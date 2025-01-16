import os
import logging
import asyncio

from fastapi_utilities import repeat_every

from indexer import Indexer
from pydantic import BaseModel
from async_queue import AsyncQueue
from fastapi import FastAPI, APIRouter
from contextlib import asynccontextmanager
from async_loop import index_loop, crawl_loop
from storage import MinimaStore
import nltk


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

START_INDEXING = os.environ.get('START_INDEXING', 'false').lower() == 'true'

indexer = Indexer()
async_queue = AsyncQueue()
router = APIRouter()
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    tasks = []
    logger.info(f"Start indexing: {START_INDEXING}")
    await schedule_reindexing()
    try:
        if START_INDEXING:
            tasks.extend([
                asyncio.create_task(crawl_loop(async_queue)),
                asyncio.create_task(index_loop(async_queue, indexer))
            ])
        yield
    finally:
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


def create_app() -> FastAPI:
    app = FastAPI(
        openapi_url="/indexer/openapi.json",
        docs_url="/indexer/docs",
        lifespan=lifespan
    )
    app.include_router(router)
    return app


app = create_app()


async def trigger_re_indexer():
    logger.info("Reindexing triggered")
    tasks = []
    try:
        tasks.extend([
            asyncio.create_task(crawl_loop(async_queue)),
            asyncio.create_task(index_loop(async_queue, indexer))
        ])
        await asyncio.gather(*tasks, return_exceptions=True)
        logger.info("reindexing finished")
    except Exception as e:
        logger.error(f"error in scheduled reindexing {e}")
    finally:
        for task in tasks:
            task.cancel()


@repeat_every(seconds=60*20)
async def schedule_reindexing():
    await trigger_re_indexer()
