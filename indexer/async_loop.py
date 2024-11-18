import os
import uuid
import asyncio
import logging
from indexer import Indexer
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)
executor = ThreadPoolExecutor()

CONTAINER_PATH = "/usr/src/app/local_files/"
AVAILABLE_EXTENSIONS = [ ".pdf", ".xls", ".docx", ".txt", ".md", ".csv" ]

async def crawl_loop(async_queue):
    logger.info(f"Starting crawl loop with path: {CONTAINER_PATH}")
    for root, _, files in os.walk(CONTAINER_PATH):
        logger.info(f"Processing folder: {root}")
        for file in files:
            if not any(file.endswith(ext) for ext in AVAILABLE_EXTENSIONS):
                logger.info(f"Skipping file: {file}")
                continue
            path = os.path.join(root, file)
            message = {
                "path": os.path.join(root, file), 
                "file_id": str(uuid.uuid4())
            }
            async_queue.enqueue(message)
            logger.info(f"File enqueue: {path}")


async def index_loop(async_queue, indexer: Indexer):
    loop = asyncio.get_running_loop()
    logger.info("Starting index loop")
    while True:
        if async_queue.size() == 0:
            logger.info("No files to index. Indexing stopped, all files indexed.")
            await asyncio.sleep(0.1)
            continue
        message = await async_queue.dequeue()
        logger.info(f"Processing message: {message}")
        try:
            await loop.run_in_executor(executor, indexer.index, message)
        except Exception as e:
            logger.error(f"Error in processing message: {e}")
            logger.error(f"Failed to process message: {message}")

