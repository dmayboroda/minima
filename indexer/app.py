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
from fastapi import FastAPI, APIRouter, UploadFile, File, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
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


def get_user_id(request: Request) -> str:
    """Extract user_id from X-User-Id header with default fallback"""
    user_id = request.headers.get("X-User-Id", "default_user")
    if user_id == "default_user":
        logger.warning("No X-User-Id header provided, using default_user")
    return user_id


class Query(BaseModel):
    query: str


class FileUploadResponse(BaseModel):
    status: str
    files: List[dict]  # Changed from List[str] to List[dict] to include status
    message: str


class FileRemoveRequest(BaseModel):
    files: List[str]


class FileRemoveResponse(BaseModel):
    status: str
    removed_files: List[str]
    message: str


class FileStatusRequest(BaseModel):
    files: List[str]


class FileStatusResponse(BaseModel):
    files: List[dict]


@router.post(
    "/query",
    response_description='Query local data storage',
)
async def query(query_request: Query, request: Request):
    user_id = get_user_id(request)
    logger.info(f"Received query: {query_request.query} (user: {user_id})")
    try:
        result = indexer.find(query_request.query, user_id=user_id)
        logger.info(f"Found {len(result)} results for query: {query_request.query}")
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
async def add_files(request: Request, files: List[UploadFile] = File(...)):
    """
    Add one or more files for indexing asynchronously.
    Files are stored in LOCAL_FILES_PATH/{user_id}/ and queued for indexing.
    """
    user_id = get_user_id(request)
    logger.info(f"Received {len(files)} files for indexing (user: {user_id})")

    # Get LOCAL_FILES_PATH from environment
    local_files_path = os.environ.get("LOCAL_FILES_PATH")
    if not local_files_path:
        logger.error("LOCAL_FILES_PATH environment variable not set")
        raise HTTPException(status_code=500, detail="LOCAL_FILES_PATH not configured")

    # Create user-specific directory
    user_dir = Path(local_files_path) / user_id
    user_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Using directory: {user_dir}")

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

            # Create file path in user directory
            file_path = user_dir / file.filename

            # Save file asynchronously
            async with aiofiles.open(file_path, 'wb') as f:
                content = await file.read()
                await f.write(content)

            logger.info(f"Saved file: {file_path}")

            # Queue file for indexing with user_id
            import time
            file_stat = os.stat(file_path)
            message = {
                "type": "file",
                "path": str(file_path),
                "file_id": str(file_path),
                "last_updated_seconds": int(file_stat.st_mtime),
                "user_id": user_id
            }
            async_queue.enqueue(message)
            logger.info(f"Queued file for indexing: {file.filename} (user: {user_id})")

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

    # Create response with file paths and initial status
    files_with_status = [
        {
            "path": fpath,
            "status": "uploaded"
        }
        for fpath in uploaded_files
    ]

    response_message = f"Successfully uploaded {len(uploaded_files)} file(s) for indexing"
    if errors:
        response_message += f". Errors: {'; '.join(errors)}"

    return FileUploadResponse(
        status="success" if uploaded_files else "partial",
        files=files_with_status,
        message=response_message
    )


@router.post(
    "/files/remove",
    response_description='Remove files from index',
    response_model=FileRemoveResponse
)
async def remove_files(remove_request: FileRemoveRequest, request: Request):
    """
    Remove one or more files from the index and Qdrant vector store.
    Files are deleted from both the SQLite database and Qdrant.
    Only removes files owned by the authenticated user.
    """
    user_id = get_user_id(request)
    logger.info(f"Received request to remove {len(remove_request.files)} files (user: {user_id})")

    if not remove_request.files:
        raise HTTPException(status_code=400, detail="No files specified for removal")

    try:
        # Remove from Qdrant vector store (with user_id filter)
        indexer.remove_from_storage(files_to_remove=remove_request.files, user_id=user_id)

        # Remove from SQLite database (with user_id filter)
        for fpath in remove_request.files:
            try:
                MinimaStore.delete_m_doc(fpath, user_id=user_id)
                logger.info(f"Removed {fpath} from database (user: {user_id})")
            except Exception as e:
                logger.warning(f"File {fpath} not found in database for user {user_id}: {str(e)}")

        return FileRemoveResponse(
            status="success",
            removed_files=remove_request.files,
            message=f"Successfully removed {len(remove_request.files)} file(s) from index"
        )
    except Exception as e:
        logger.error(f"Error removing files: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to remove files: {str(e)}")


@router.get(
    "/files/stats",
    response_description='Get indexing statistics'
)
async def get_indexing_stats(request: Request):
    """
    Get indexing statistics including:
    - Total number of indexed files
    - Total indexing time
    - Average indexing time per file
    - Individual file indexing times
    Filtered by user_id.
    """
    user_id = get_user_id(request)
    logger.info(f"Received request for indexing statistics (user: {user_id})")
    try:
        stats = MinimaStore.get_indexing_stats(user_id=user_id)
        return stats
    except Exception as e:
        logger.error(f"Error retrieving indexing stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve stats: {str(e)}")


@router.post(
    "/files/status",
    response_description='Check indexing status of files',
    response_model=FileStatusResponse
)
async def check_files_status(status_request: FileStatusRequest, request: Request):
    """
    Check the indexing status of specific files.
    Returns status for each file: uploaded, indexing, indexed, or failed.
    UI can poll this endpoint to show loading indicators.
    Filtered by user_id.
    """
    user_id = get_user_id(request)
    logger.info(f"Received status check for {len(status_request.files)} files (user: {user_id})")

    if not status_request.files:
        raise HTTPException(status_code=400, detail="No files specified")

    try:
        files_status = MinimaStore.get_files_status(status_request.files, user_id=user_id)
        return FileStatusResponse(files=files_status)
    except Exception as e:
        logger.error(f"Error retrieving file status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve status: {str(e)}")


@router.get(
    "/files",
    response_description='List all files in the index'
)
async def list_indexed_files(request: Request):
    """
    Get a list of all files currently in the index for the authenticated user.
    Returns file path, status, indexing time, and last updated timestamp for each file.
    """
    user_id = get_user_id(request)
    logger.info(f"Received request to list all indexed files (user: {user_id})")
    try:
        docs = MinimaStore.get_all_docs(user_id=user_id)
        files = [
            {
                "path": doc.fpath,
                "status": doc.status,
                "indexing_time_seconds": round(doc.indexing_time_seconds, 2) if doc.indexing_time_seconds else None,
                "last_updated": doc.last_updated_seconds
            }
            for doc in docs
        ]
        return {
            "total": len(files),
            "files": files
        }
    except Exception as e:
        logger.error(f"Error listing indexed files: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to list files: {str(e)}")


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

    # Add CORS middleware to allow frontend requests
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://localhost:3001"],  # React dev server
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
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


@repeat_every(seconds=15)
async def schedule_reindexing():
    await trigger_re_indexer()

app = create_app()