import requests
import logging
from typing import Any, List
from pydantic import BaseModel
from langchain_core.embeddings import Embeddings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

REQUEST_DATA_URL = "http://indexer:8000/embedding"
REQUEST_HEADERS = {
    'Accept': 'application/json',
    'Content-Type': 'application/json'
}

class MinimaEmbeddings(BaseModel, Embeddings):

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        results = []
        for text in texts:
            embedding = self.request_data(text)
            if "error" in embedding:
                logger.error(f"Error in embedding: {embedding['error']}")
            else:
                embedding = embedding["result"]
                results.append(embedding)
        return results

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]

    def request_data(self, query):
        payload = {
            "query": query
        }
        try:
            logger.info(f"Requesting data from indexer with query: {query}")
            response = requests.post(REQUEST_DATA_URL, headers=REQUEST_HEADERS, json=payload)
            response.raise_for_status()
            data = response.json()
            logger.info(f"Received data: {data}")
            return data

        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP error: {e}")
            return {"error": str(e)}