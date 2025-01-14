import logging
import mcp.server.stdio
from typing import Annotated
from mcp.server import Server
from .requestor import request_data
from pydantic import BaseModel, Field
from mcp.server.stdio import stdio_server
from mcp.shared.exceptions import McpError
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions
from mcp.types import (
    GetPromptResult,
    Prompt,
    PromptArgument,
    PromptMessage,
    TextContent,
    Tool,
    INVALID_PARAMS,
    INTERNAL_ERROR,
    Resource
)
from os import getenv
from urllib.parse import quote

FILE_URL_PREFIX = getenv("FILE_URL_PREFIX", "http://localhost:8000/files/files")


logging.basicConfig(
    level=logging.DEBUG, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)

server = Server("minima")

class Query(BaseModel):
    text: Annotated[
        str, 
        Field(description="context to find")
    ]
    pool: Annotated[
        str, 
        Field(description="the pool to search in")
    ]

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="rag_query",
            description=(
                "Usees a RAG model to find context in indexed documents (PDF, CSV, DOCX, HTML, MD, TXT). "  
                "All documents are orqanized in pools. A pool to search in must be specified. "
                "The tool provides a list of relevant documents, and separately the context from those documents. "
                "The links received are URLs directly linking to the documents. "
                ""
                "For all responses, the links to the relevant documents MUST be provided. "
                "Answers must be annotated with the clickable HTTPS URLs to the relevant documents used to gerenate the response. "
                "Every major statement made in the response must directly link to the source document. "
                "These links should be formatted in bold face and italics and be called 'source'."
                ""
                "Arguments: "
                " - text: The text context to search for. "
                " - pool: The pool to search in. "
            ),
            inputSchema=Query.model_json_schema(),
        )
    ]

@server.list_resources()
async def list_resources() -> list[Resource]:
    return [
    ]

@server.list_prompts()
async def list_prompts() -> list[Prompt]:
    logging.info("List of prompts")
    return [
        Prompt(
            name="rag_query",
            description="Find a context in a document pool",
            arguments=[
                PromptArgument(
                    name="context", description="Context to search", required=True
                ),
                PromptArgument(
                    name="pool", description="The Document pool to search", required=True
                ),
                
            ]
        )            
    ]
    
@server.call_tool()
async def call_tool(name, arguments: dict) -> list[TextContent]:
    if name != "rag_query":
        logging.error(f"Unknown tool: {name}")
        raise ValueError(f"Unknown tool: {name}")

    logging.info("Calling tools")
    try:
        logging.info(f"Arguments: {arguments}")
        args = Query(**arguments)
    except ValueError as e:
        logging.error(str(e))
        raise McpError(INVALID_PARAMS, str(e))
        
    context = args.text
    pool = args.pool
    logging.info(f"Context: {context}, pool: {pool}")
    if not context:
        logging.error("Context is required")
        raise McpError(INVALID_PARAMS, "Context is required")

    output = await request_data(context, pool)
    if "error" in output:
        logging.error(output["error"])
        raise McpError(INTERNAL_ERROR, output["error"])
    
    logging.info(f"Got prompt")    
    text = "# Relevant context:\n\n" + str(output['result']['output'])
    links = output['result']['links']
    logging.info(f"links: {links}")    
    https_links = [f"* [{l}]({FILE_URL_PREFIX}/{quote(l.replace('file:///',''))})" for l in links]
    logging.info(f"Got prompt {https_links}")  
    links = "# Relevant files:\n\n" + '\n'.join(https_links)
    result = []
    logging.info(f"Links: {links}")
    result.append(TextContent(type="text", text=links))
    result.append(TextContent(type="text", text=text))
    logging.info(f"result: {output}")
    return result
    
@server.get_prompt()
async def get_prompt(name: str, arguments: dict | None) -> GetPromptResult:
    if not arguments or "context" not in arguments or "pool" not in arguments:
        logging.error("Context and pool are required")
        raise McpError(INVALID_PARAMS, "Context and pool are required")
        
    context = arguments["context"]
    pool = arguments["pool"]

    output = await request_data(context, pool)
    if "error" in output:
        error = output["error"]
        logging.error(error)
        return GetPromptResult(
            description=f"Faild to find a {context}",
            messages=[
                PromptMessage(
                    role="user", 
                    content=TextContent(type="text", text=error),
                )
            ]
        )

    logging.info(f"Get prompt: {output}")    
    output = output['result']['output']
    return GetPromptResult(
        description=f"Found content for this {context}",
        messages=[
            PromptMessage(
                role="user", 
                content=TextContent(type="text", text=output)
            )
        ]
    )

async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="minima",
                server_version="0.0.1",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )