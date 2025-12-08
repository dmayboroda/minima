import nltk
import logging
import asyncio
import os
import aiofiles
from pathlib import Path
from typing import List
from indexer import Indexer
from pydantic import BaseModel
from storage import MinimaStore
from async_queue import AsyncQueue
from fastapi import FastAPI, APIRouter, UploadFile, File, HTTPException
from contextlib import asynccontextmanager
from fastapi_utilities import repeat_every
from async_loop import index_loop, crawl_loop

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {
    ".pdf", 
    ".xls", 
    ".xlsx", 
    ".doc", 
    ".docx", 
    ".txt", 
    ".md", 
    ".csv", 
    ".ppt", 
    ".pptx"
}

indexer = Indexer()
router = APIRouter()
async_queue = AsyncQueue()
MinimaStore.create_db_and_tables()

def init_loader_dependencies():
    nltk.download('punkt')
    nltk.download('punkt_tab')
    nltk.download('wordnet')
    nltk.download('omw-1.4')
    nltk.download('punkt')
    nltk.download('averaged_perceptron_tagger_eng')

init_loader_dependencies()

class Query(BaseModel):
    query: str


class FileUploadResponse(BaseModel):
    status: str
    files: List[str]
    message: str


@router.post(
    "/query", 
    response_description='Query local data storage',
)
async def query(request: Query):
    logger.info(f"Received query: {query}")
    try:
        result = indexer.find(request.query)
        logger.info(f"Found {len(result)} results for query: {query}")
        logger.info(f"Results: {result}")
        return {"result": result}
    except Exception as e:
        logger.error(f"Error in processing query: {e}")
        return {"error": str(e)}


@router.post(
    "/embedding",
    response_description='Get embedding for a query',
)
async def embedding(request: Query):
    logger.info(f"Received embedding request: {request}")
    try:
        result = indexer.embed(request.query)
        logger.info(f"Found {len(result)} results for query: {request.query}")
        return {"result": result}
    except Exception as e:
        logger.error(f"Error in processing embedding: {e}")
        return {"error": str(e)}


@router.post(
    "/files/add",
    response_description='Add files for indexing',
    response_model=FileUploadResponse
)
async def add_files(files: List[UploadFile] = File(...)):
    """
    Add one or more files for indexing asynchronously.
    Files are stored in LOCAL_FILES_PATH and queued for indexing.
    """
    logger.info(f"Received {len(files)} files for indexing")

    # Get LOCAL_FILES_PATH from environment
    local_files_path = os.environ.get("LOCAL_FILES_PATH")
    if not local_files_path:
        logger.error("LOCAL_FILES_PATH environment variable not set")
        raise HTTPException(status_code=500, detail="LOCAL_FILES_PATH not configured")

    # Ensure the directory exists
    Path(local_files_path).mkdir(parents=True, exist_ok=True)

    uploaded_files = []
    errors = []

    # Process each file asynchronously
    async def save_file(file: UploadFile):
        try:
            # Validate file extension
            file_ext = Path(file.filename).suffix.lower()
            if file_ext not in SUPPORTED_EXTENSIONS:
                error_msg = f"Unsupported file type: {file.filename} (supported: {', '.join(SUPPORTED_EXTENSIONS)})"
                logger.warning(error_msg)
                errors.append(error_msg)
                return None

            # Create file path
            file_path = Path(local_files_path) / file.filename

            # Save file asynchronously
            async with aiofiles.open(file_path, 'wb') as f:
                content = await file.read()
                await f.write(content)

            logger.info(f"Saved file: {file_path}")

            # Queue file for indexing
            import time
            file_stat = os.stat(file_path)
            message = {
                "type": "file",
                "path": str(file_path),
                "file_id": str(file_path),
                "last_updated_seconds": int(file_stat.st_mtime)
            }
            async_queue.enqueue(message)
            logger.info(f"Queued file for indexing: {file.filename}")

            return str(file_path)
        except Exception as e:
            error_msg = f"Error processing {file.filename}: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
            return None

    # Save all files concurrently
    results = await asyncio.gather(*[save_file(file) for file in files])
    uploaded_files = [r for r in results if r is not None]

    if not uploaded_files and errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))

    response_message = f"Successfully uploaded {len(uploaded_files)} file(s) for indexing"
    if errors:
        response_message += f". Errors: {'; '.join(errors)}"

    return FileUploadResponse(
        status="success" if uploaded_files else "partial",
        files=uploaded_files,
        message=response_message
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    tasks = [
        asyncio.create_task(crawl_loop(async_queue)),
        asyncio.create_task(index_loop(async_queue, indexer))
    ]
    await schedule_reindexing()
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


def create_app() -> FastAPI:
    app = FastAPI(
        openapi_url="/indexer/openapi.json",
        docs_url="/indexer/docs",
        lifespan=lifespan
    )
    app.include_router(router)
    return app

async def trigger_re_indexer():
    logger.info("Reindexing triggered")
    try:
        await asyncio.gather(
            crawl_loop(async_queue),
            index_loop(async_queue, indexer)
        )
        logger.info("reindexing finished")
    except Exception as e:
        logger.error(f"error in scheduled reindexing {e}")


@repeat_every(seconds=60*2)
async def schedule_reindexing():
    await trigger_re_indexer()

app = create_app()