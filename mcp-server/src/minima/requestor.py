import httpx
import logging
from os import getenv


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

REQUEST_DATA_URL = getenv("REQUEST_DATA_URL", "http://localhost:8001/query")
REQUEST_HEADERS = {
    'Accept': 'application/json',
    'Content-Type': 'application/json'
}

async def request_data(query, pool):
    payload = {
        "query": query,
        "pool": pool
    }
    async with httpx.AsyncClient() as client:
        try:
            logger.info(f"Requesting data from indexer with query: {query}")
            response = await client.post(REQUEST_DATA_URL, 
                                         headers=REQUEST_HEADERS, 
                                         json=payload)
            response.raise_for_status()
            data = response.json()
            logger.debug(f"Received data: {data}")
            return data

        except Exception as e:
            logger.error(f"HTTP error: {e}")
            return { "error": str(e) }