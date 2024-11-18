import os
import uuid
import datetime
import logging
from langchain import hub
from typing import Sequence
from qdrant_client import QdrantClient
from langchain_ollama import ChatOllama
from minima_embed import MinimaEmbeddings
from langgraph.graph import START, StateGraph
from langchain_qdrant import QdrantVectorStore
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import Annotated, TypedDict
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import AIMessage, HumanMessage
from langchain.chains.retrieval import create_retrieval_chain
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.chains.combine_documents import create_stuff_documents_chain
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

QDRANT_COLLECTION = "mnm_storage"
QDRANT_BOOTSTRAP = "qdrant"
OLLAMA_MODEL = "qwen2:0.5b"

class State(TypedDict):
    input: str
    chat_history: Annotated[Sequence[BaseMessage], add_messages]
    context: str
    answer: str

class LLMChain:
    def __init__(self):
        llm = ChatOllama(
            base_url="http://ollama:11434",
            model=OLLAMA_MODEL,
            temperature=0.5
        )
        qdrant = QdrantClient(host=QDRANT_BOOTSTRAP)
        
        embed_model = MinimaEmbeddings()

        self.document_store = QdrantVectorStore(
            client=qdrant,
            collection_name=QDRANT_COLLECTION,
            embedding=embed_model
        )

        contextualize_q_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", CONTEXTUALIZE_Q_SYSTEM_PROMPT),
                MessagesPlaceholder("chat_history"),
                ("human", "{input}"),
            ]
        )

        history_aware_retriever = create_history_aware_retriever(
            llm, self.document_store.as_retriever(), contextualize_q_prompt
        )

        qa_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", SYSTEM_PROMPT),
                MessagesPlaceholder("chat_history"),
                ("human", "{input}"),
            ]
        )

        question_answer_chain = create_stuff_documents_chain(llm, qa_prompt)
        self.chain = create_retrieval_chain(history_aware_retriever, question_answer_chain)
        self.graph = self._create_graph()

    def _create_graph(self) -> StateGraph:
        workflow = StateGraph(state_schema=State)
        workflow.add_edge(START, "model")
        workflow.add_node("model", self._call_model)
        memory = MemorySaver()
        app = workflow.compile(checkpointer=memory)
        logger.info("Graph created.")
        return app

    def _call_model(self, state: State):
        logger.info(f"Processing query: {state['input']}")
        response = self.chain.invoke(state)
        logger.info(f"Received response: {response['answer']}")
        return {
            "chat_history": [
                HumanMessage(state["input"]),
                AIMessage(response["answer"]),
            ],
            "context": response["context"],
            "answer": response["answer"],
        }
    
    def invoke(self, message: str):
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
            return result["answer"]
        except Exception as e:
            logger.error(f"Error in processing query: {e}")
            return {"error": str(e)}