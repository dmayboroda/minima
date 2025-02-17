import os
import uuid
import torch
import datetime
import logging
from dataclasses import dataclass
from typing import Sequence, Optional
from langchain.schema import Document
from qdrant_client import QdrantClient
from langchain_ollama import ChatOllama
from minima_embed import MinimaEmbeddings
from langgraph.graph import START, StateGraph
from langchain_qdrant import QdrantVectorStore
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import Annotated, TypedDict
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.messages import AIMessage, HumanMessage
from langchain.chains.retrieval import create_retrieval_chain
from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import CrossEncoderReranker
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_community.cross_encoders.huggingface import HuggingFaceCrossEncoder
from langchain.chains.history_aware_retriever import create_history_aware_retriever

logger = logging.getLogger(__name__)

CONTEXTUALIZE_Q_SYSTEM_PROMPT = (
    "Given a chat history and the latest user question "
    "which might reference context in the chat history, "
    "formulate a standalone question which can be understood "
    "without the chat history. Do NOT answer the question, "
    "just reformulate it if needed and otherwise return it as is."
)

SYSTEM_PROMPT = (
    "You are an assistant for question-answering tasks. "
    "Use the following pieces of retrieved context to answer "
    "the question. If you don't know the answer, say that you "
    "don't know. Use three sentences maximum and keep the "
    "answer concise."
    "\n\n"
    "{context}"
)

QUERY_ENHANCEMENT_PROMPT = (
    "You are an expert at converting user questions into queries."
    "You have access to a users files."
    "Perform query expansion."
    "Just return one expanded query, do not add any other text."
    "If there are acronyms or words you are not familiar with, do not try to rephrase them."
    "Do not change the original meaning of the question and do not add any additional information."
)

class ParaphrasedQuery(BaseModel):
    paraphrased_query: str = Field(
        ...,
        description="A unique paraphrasing of the original question.",
    )

@dataclass
class LLMConfig:
    """Configuration settings for the LLM Chain"""
    qdrant_collection: str = "mnm_storage"
    qdrant_host: str = "qdrant"
    ollama_url: str = "http://ollama:11434"
    ollama_model: str = os.environ.get("OLLAMA_MODEL")
    rerank_model: str = os.environ.get("RERANKER_MODEL")
    temperature: float = 0.5
    device: torch.device = torch.device(
        "mps" if torch.backends.mps.is_available() else
        "cuda" if torch.cuda.is_available() else
        "cpu"
    )


@dataclass
class LocalConfig:
    LOCAL_FILES_PATH = os.environ.get("LOCAL_FILES_PATH")
    CONTAINER_PATH = os.environ.get("CONTAINER_PATH")


class State(TypedDict):
    """State definition for the LLM Chain"""
    input: str
    chat_history: Annotated[Sequence[BaseMessage], add_messages]
    context: str
    answer: str
    init_query: str


class LLMChain:
    """A chain for processing LLM queries with context awareness and retrieval capabilities"""

    def __init__(self, config: Optional[LLMConfig] = None):
        """Initialize the LLM Chain with optional custom configuration"""
        self.localConfig = LocalConfig()
        self.config = config or LLMConfig()
        self.llm = self._setup_llm()
        self.document_store = self._setup_document_store()
        self.chain = self._setup_chain()
        self.graph = self._create_graph()

    def _setup_llm(self) -> ChatOllama:
        """Initialize the LLM model"""
        return ChatOllama(
            base_url=self.config.ollama_url,
            model=self.config.ollama_model,
            temperature=self.config.temperature
        )

    def _setup_document_store(self) -> QdrantVectorStore:
        """Initialize the document store with vector embeddings"""
        qdrant = QdrantClient(host=self.config.qdrant_host)
        embed_model = MinimaEmbeddings()
        return QdrantVectorStore(
            client=qdrant,
            collection_name=self.config.qdrant_collection,
            embedding=embed_model
        )

    def _setup_chain(self):
        """Set up the retrieval and QA chain"""
        # Initialize retriever with reranking
        base_retriever = self.document_store.as_retriever()
        reranker = HuggingFaceCrossEncoder(
            model_name=self.config.rerank_model,
            model_kwargs={'device': self.config.device},
        )
        compression_retriever = ContextualCompressionRetriever(
            base_compressor=CrossEncoderReranker(model=reranker, top_n=3),
            base_retriever=base_retriever
        )

        # Create history-aware retriever
        contextualize_prompt = ChatPromptTemplate.from_messages([
            ("system", CONTEXTUALIZE_Q_SYSTEM_PROMPT),
            MessagesPlaceholder("chat_history"),
            ("human", "{input}"),
        ])
        history_aware_retriever = create_history_aware_retriever(
            self.llm, compression_retriever, contextualize_prompt
        )

        # Create QA chain
        qa_prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            MessagesPlaceholder("chat_history"),
            ("human", "{input}"),
        ])
        qa_chain = create_stuff_documents_chain(self.llm, qa_prompt)
        retrieval_chain = create_retrieval_chain(history_aware_retriever, qa_chain)

        return retrieval_chain

    def _create_graph(self) -> StateGraph:
        """Create the processing graph"""
        workflow = StateGraph(state_schema=State)
        workflow.add_node("enhance", self._enhance_query)
        workflow.add_node("retrieval", self._call_model)
        workflow.add_edge(START, "enhance")
        workflow.add_edge("enhance", "retrieval")
        return workflow.compile(checkpointer=MemorySaver())

    def _enhance_query(self, state: State) -> str:
        """Enhance the query using the LLM"""
        prompt_enhancement = ChatPromptTemplate.from_messages([
            ("system", QUERY_ENHANCEMENT_PROMPT),
            ("human", "{input}"),
        ])
        query_enhancement = prompt_enhancement | self.llm
        enhanced_query = query_enhancement.invoke({
            "input": state["input"]
        })
        logger.info(f"Enhanced query: {enhanced_query}")
        state["init_query"] = state["input"]
        state["input"] = enhanced_query.content
        return state

    def _call_model(self, state: State) -> dict:
        """Process the query through the model"""
        logger.info(f"Processing query: {state['init_query']}")
        logger.info(f"Enhanced query: {state['input']}")
        response = self.chain.invoke(state)
        logger.info(f"Received response: {response['answer']}")
        return {
            "chat_history": [
                HumanMessage(state["init_query"]),
                AIMessage(response["answer"]),
            ],
            "context": response["context"],
            "answer": response["answer"],
        }
    
    def invoke(self, message: str) -> dict:
        """
        Process a user message and return the response
        
        Args:
            message: The user's input message
            
        Returns:
            dict: Contains the model's response or error information
        """
        try:
            logger.info(f"Processing query: {message}")
            config = {
                "configurable": {
                    "thread_id": uuid.uuid4(),
                    "thread_ts": datetime.datetime.now().isoformat()
                }   
            }
            result = self.graph.invoke(
                {"input": message},
                config=config
            )
            logger.info(f"OUTPUT: {result}")
            links = set()
            for ctx in result["context"]:
                doc: Document = ctx
                path = doc.metadata["file_path"].replace(
                    self.localConfig.CONTAINER_PATH,
                    self.localConfig.LOCAL_FILES_PATH
                )
                links.add(f"file://{path}")
            return {"answer": result["answer"], "links": links}
        except Exception as e:
            logger.error(f"Error processing query", exc_info=True)
            return {"error": str(e), "status": "error"}