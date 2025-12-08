import os
import re
import uuid
import datetime
import logging
from dataclasses import dataclass
from typing import Sequence, Optional, List
from langchain.schema import Document
from qdrant_client import QdrantClient
from langchain_openai import ChatOpenAI
from minima_embed import MinimaEmbeddings
from langgraph.graph import START, StateGraph
from langchain_qdrant import QdrantVectorStore
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, ToolMessage
from langgraph.graph.message import add_messages
from typing_extensions import Annotated, TypedDict
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# OpenAI workflow prompt
OPENAI_SYSTEM_PROMPT = (
    "You are a helpful assistant that answers questions about documents. "
    "You have access to a search_documents tool that allows you to search through a user's local files. "
    "When a user asks a question that requires information from their documents, use the search_documents tool. "
    "After receiving the search results, provide a comprehensive answer based on the retrieved context. "
    "If you don't find relevant information in the documents, say so clearly. "
    "Always cite which documents you found the information in."
)


@dataclass
class OpenAIConfig:
    """Configuration settings for the OpenAI LLM Chain"""
    qdrant_collection: str = "mnm_storage"
    qdrant_host: str = "qdrant"
    llm_base_url: str = os.environ.get("LLM_BASE_URL")
    llm_model: str = os.environ.get("LLM_MODEL")
    llm_api_key: str = os.environ.get("LLM_API_KEY", "not-needed")
    temperature: float = 0.5


@dataclass
class LocalConfig:
    LOCAL_FILES_PATH = os.environ.get("LOCAL_FILES_PATH")
    CONTAINER_PATH = os.environ.get("CONTAINER_PATH")


class OpenAIState(TypedDict):
    """State definition for the OpenAI LLM Chain"""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    context: Optional[List[Document]]
    answer: str


class OpenAIChain:
    """OpenAI-based RAG chain with tool calling for document retrieval"""

    def __init__(self, config: Optional[OpenAIConfig] = None):
        """Initialize the OpenAI Chain with optional custom configuration"""
        self.localConfig = LocalConfig()
        self.config = config or OpenAIConfig()
        self.llm = self._setup_llm()
        self.document_store = self._setup_document_store()
        self.graph = self._create_graph()

    def _setup_llm(self) -> ChatOpenAI:
        """Initialize the OpenAI-compatible LLM model"""
        logger.info(f"Using custom LLM at {self.config.llm_base_url} with model {self.config.llm_model}")
        return ChatOpenAI(
            base_url=self.config.llm_base_url,
            model=self.config.llm_model,
            api_key=self.config.llm_api_key,
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

    def _create_search_tool(self):
        """Create a search tool for document retrieval"""
        @tool
        def search_documents(query: str) -> str:
            """
            Search through the user's local documents to find relevant information.

            Args:
                query: The search query to find relevant documents

            Returns:
                A string containing the relevant document excerpts
            """
            logger.info(f"Searching documents for: {query}")

            # Use basic retriever without reranking for OpenAI workflow
            retriever = self.document_store.as_retriever(search_kwargs={"k": 5})
            docs = retriever.invoke(query)

            if not docs:
                return "No relevant documents found."

            # Format results
            results = []
            for i, doc in enumerate(docs, 1):
                file_path = doc.metadata.get("file_path", "Unknown")
                content = doc.page_content
                results.append(f"[Document {i} - {file_path}]\n{content}\n")

            logger.info(f"Found {len(docs)} relevant documents")
            return "\n".join(results)

        return search_documents

    def _create_graph(self) -> StateGraph:
        """Create the processing graph with tool-based retrieval"""
        # Create search tool
        search_tool = self._create_search_tool()

        # Bind tool to LLM
        llm_with_tools = self.llm.bind_tools([search_tool])

        workflow = StateGraph(state_schema=OpenAIState)
        workflow.add_node("agent", lambda state: self._call_agent(state, llm_with_tools))
        workflow.add_node("tools", self._execute_tools)
        workflow.add_edge(START, "agent")
        workflow.add_conditional_edges(
            "agent",
            self._should_continue,
            {
                "tools": "tools",
                "end": "__end__"
            }
        )
        workflow.add_edge("tools", "agent")
        return workflow.compile(checkpointer=MemorySaver())

    def _call_agent(self, state: OpenAIState, llm_with_tools) -> dict:
        """Call the OpenAI LLM with tool support"""
        messages = state["messages"]

        # Add system message if this is the first message
        if not any(isinstance(msg, type(messages[0])) and hasattr(msg, 'type') and msg.type == "system" for msg in messages):
            messages = [{"role": "system", "content": OPENAI_SYSTEM_PROMPT}] + list(messages)

        logger.info(f"Calling OpenAI agent with {len(messages)} messages")
        response = llm_with_tools.invoke(messages)
        logger.info(f"OpenAI agent response: {response}")

        return {"messages": [response]}

    def _execute_tools(self, state: OpenAIState) -> dict:
        """Execute the tool calls made by the LLM"""
        messages = state["messages"]
        last_message = messages[-1]

        logger.info(f"Executing tools for message: {last_message}")

        # Get tool calls from the last message
        tool_calls = last_message.tool_calls if hasattr(last_message, 'tool_calls') else []

        if not tool_calls:
            logger.warning("No tool calls found in last message")
            return {"messages": []}

        # Execute each tool call
        tool_messages = []
        search_tool = self._create_search_tool()

        for tool_call in tool_calls:
            logger.info(f"Executing tool: {tool_call}")
            tool_name = tool_call.get("name", "")
            tool_args = tool_call.get("args", {})
            tool_id = tool_call.get("id", "")

            if tool_name == "search_documents":
                result = search_tool.invoke(tool_args)
                tool_messages.append(
                    ToolMessage(content=result, tool_call_id=tool_id)
                )

        logger.info(f"Executed {len(tool_messages)} tools")
        return {"messages": tool_messages}

    def _should_continue(self, state: OpenAIState) -> str:
        """Determine if we should continue to tools or end"""
        messages = state["messages"]
        last_message = messages[-1]

        # If there are tool calls, continue to tools node
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            logger.info("Continuing to tools")
            return "tools"

        # Otherwise, end
        logger.info("Ending workflow")
        return "end"

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
                {"messages": [HumanMessage(content=message)]},
                config=config
            )
            logger.info(f"OpenAI OUTPUT: {result}")

            # Extract answer from the last AI message
            messages = result["messages"]
            answer = ""
            for msg in reversed(messages):
                if isinstance(msg, AIMessage) and not hasattr(msg, 'tool_calls'):
                    answer = msg.content
                    break
                elif isinstance(msg, AIMessage) and (msg.tool_calls is None or len(msg.tool_calls) == 0):
                    answer = msg.content
                    break

            # Extract links from tool messages (document searches)
            links = set()
            for msg in messages:
                if hasattr(msg, 'name') and msg.name == "search_documents":
                    # Parse file paths from tool results
                    file_pattern = r'\[Document \d+ - (.+?)\]'
                    matches = re.findall(file_pattern, str(msg.content))
                    for match in matches:
                        # Convert container path to local path
                        path = match.replace(
                            self.localConfig.CONTAINER_PATH,
                            self.localConfig.LOCAL_FILES_PATH
                        )
                        links.add(f"file://{path}")

            return {"answer": answer, "links": links}
        except Exception as e:
            logger.error(f"Error processing query", exc_info=True)
            return {"error": str(e), "status": "error"}
