import os
import uuid
import torch
import logging
import time
from dataclasses import dataclass
from typing import List, Dict
from pathlib import Path

from qdrant_client import QdrantClient
from langchain_qdrant import QdrantVectorStore
from langchain_huggingface import HuggingFaceEmbeddings
from qdrant_client.http.models import (
    Distance, 
    VectorParams, 
    Filter, 
    FieldCondition, 
    MatchValue
)
from langchain_text_splitters import RecursiveCharacterTextSplitter

from langchain_community.document_loaders import (
    TextLoader,
    CSVLoader,
    Docx2txtLoader,
    UnstructuredExcelLoader,
    PyMuPDFLoader,
    UnstructuredPowerPointLoader,
)

from storage import MinimaStore, IndexingStatus, FileStatus

logger = logging.getLogger(__name__)


@dataclass
class Config:
    EXTENSIONS_TO_LOADERS = {
        ".pdf": PyMuPDFLoader,
        ".pptx": UnstructuredPowerPointLoader,
        ".ppt": UnstructuredPowerPointLoader,
        ".xls": UnstructuredExcelLoader,
        ".xlsx": UnstructuredExcelLoader,
        ".docx": Docx2txtLoader,
        ".doc": Docx2txtLoader,
        ".txt": TextLoader,
        ".md": TextLoader,
        ".csv": CSVLoader,
    }
    
    DEVICE = torch.device(
        "mps" if torch.backends.mps.is_available() else
        "cuda" if torch.cuda.is_available() else
        "cpu"
    )
    
    START_INDEXING = os.environ.get("START_INDEXING")
    LOCAL_FILES_PATH = os.environ.get("LOCAL_FILES_PATH")
    CONTAINER_PATH = os.environ.get("CONTAINER_PATH")
    QDRANT_COLLECTION = "mnm_storage"
    QDRANT_BOOTSTRAP = "qdrant"
    EMBEDDING_MODEL_ID = os.environ.get("EMBEDDING_MODEL_ID")
    EMBEDDING_SIZE = os.environ.get("EMBEDDING_SIZE")
    
    CHUNK_SIZE = 500
    CHUNK_OVERLAP = 200

class Indexer:
    def __init__(self):
        self.config = Config()
        self.qdrant = self._initialize_qdrant()
        self.embed_model = self._initialize_embeddings()
        self.document_store = self._setup_collection()
        self.text_splitter = self._initialize_text_splitter()

    def _initialize_qdrant(self) -> QdrantClient:
        return QdrantClient(host=self.config.QDRANT_BOOTSTRAP)

    def _initialize_embeddings(self) -> HuggingFaceEmbeddings:
        return HuggingFaceEmbeddings(
            model_name=self.config.EMBEDDING_MODEL_ID,
            model_kwargs={'device': self.config.DEVICE},
            encode_kwargs={'normalize_embeddings': False}
        )

    def _initialize_text_splitter(self) -> RecursiveCharacterTextSplitter:
        return RecursiveCharacterTextSplitter(
            chunk_size=self.config.CHUNK_SIZE,
            chunk_overlap=self.config.CHUNK_OVERLAP
        )

    def _setup_collection(self) -> QdrantVectorStore:
        if not self.qdrant.collection_exists(self.config.QDRANT_COLLECTION):
            self.qdrant.create_collection(
                collection_name=self.config.QDRANT_COLLECTION,
                vectors_config=VectorParams(
                    size=self.config.EMBEDDING_SIZE,
                    distance=Distance.COSINE
                ),
            )
        self.qdrant.create_payload_index(
            collection_name=self.config.QDRANT_COLLECTION,
            field_name="fpath",
            field_schema="keyword"
        )
        return QdrantVectorStore(
            client=self.qdrant,
            collection_name=self.config.QDRANT_COLLECTION,
            embedding=self.embed_model,
        )

    def _create_loader(self, file_path: str):
        file_extension = Path(file_path).suffix.lower()
        loader_class = self.config.EXTENSIONS_TO_LOADERS.get(file_extension)
        
        if not loader_class:
            raise ValueError(f"Unsupported file type: {file_extension}")
        
        return loader_class(file_path=file_path)

    def _process_file(self, loader) -> List[str]:
        try:
            documents = loader.load_and_split(self.text_splitter)
            if not documents:
                logger.warning(f"No documents loaded from {loader.file_path}")
                return []

            for doc in documents:
                doc.metadata['file_path'] = loader.file_path

            uuids = [str(uuid.uuid4()) for _ in range(len(documents))]
            ids = self.document_store.add_documents(documents=documents, ids=uuids)
            
            logger.info(f"Successfully processed {len(ids)} documents from {loader.file_path}")
            return ids
            
        except Exception as e:
            logger.error(f"Error processing file {loader.file_path}: {str(e)}")
            return []

    def index(self, message: Dict[str, any]) -> None:
        start = time.time()
        path, file_id, last_updated_seconds = message["path"], message["file_id"], message["last_updated_seconds"]
        logger.info(f"Processing file: {path} (ID: {file_id})")
        indexing_status: IndexingStatus = MinimaStore.check_needs_indexing(fpath=path, last_updated_seconds=last_updated_seconds)
        if indexing_status != IndexingStatus.no_need_reindexing:
            logger.info(f"Indexing needed for {path} with status: {indexing_status}")

            # Set status to indexing
            MinimaStore.update_file_status(fpath=path, status=FileStatus.indexing)

            try:
                if indexing_status == IndexingStatus.need_reindexing:
                    logger.info(f"Removing {path} from index storage for reindexing")
                    self.remove_from_storage(files_to_remove=[path])
                loader = self._create_loader(path)
                ids = self._process_file(loader)
                if ids:
                    logger.info(f"Successfully indexed {path} with IDs: {ids}")
                    # Set status to indexed
                    MinimaStore.update_file_status(fpath=path, status=FileStatus.indexed)
                else:
                    logger.warning(f"No documents indexed for {path}")
                    MinimaStore.update_file_status(fpath=path, status=FileStatus.failed)
            except Exception as e:
                logger.error(f"Failed to index file {path}: {str(e)}")
                # Set status to failed
                MinimaStore.update_file_status(fpath=path, status=FileStatus.failed)
        else:
            logger.info(f"Skipping {path}, no indexing required. timestamp didn't change")
        end = time.time()
        indexing_time = end - start
        logger.info(f"Processing took {indexing_time} seconds for file {path}")

        # Save indexing time to database
        if indexing_status != IndexingStatus.no_need_reindexing:
            MinimaStore.update_indexing_time(fpath=path, indexing_time_seconds=indexing_time)

    def purge(self, message: Dict[str, any]) -> None:
        # Disabled automatic purge - files should only be removed via /files/remove API
        logger.info("Purge called but automatic removal is disabled. Use /files/remove API to remove files.")
        # existing_file_paths: list[str] = message["existing_file_paths"]
        # files_to_remove = MinimaStore.find_removed_files(existing_file_paths=set(existing_file_paths))
        # if len(files_to_remove) > 0:
        #     logger.info(f"purge processing removing old files {files_to_remove}")
        #     self.remove_from_storage(files_to_remove)
        # else:
        #     logger.info("Nothing to purge")

    def remove_from_storage(self, files_to_remove: list[str]):
        filter_conditions = Filter(
            must=[
                FieldCondition(
                    key="fpath",
                    match=MatchValue(value=fpath)
                )
                for fpath in files_to_remove
            ]
        )
        response = self.qdrant.delete(
            collection_name=self.config.QDRANT_COLLECTION,
            points_selector=filter_conditions,
            wait=True
        )
        logger.info(f"Delete response for {len(files_to_remove)} for files: {files_to_remove} is: {response}")

    def find(self, query: str) -> Dict[str, any]:
        try:
            logger.info(f"Searching for: {query}")
            found = self.document_store.search(query, search_type="similarity")
            
            if not found:
                logger.info("No results found")
                return {"links": set(), "output": ""}

            links = set()
            results = []
            
            for item in found:
                path = item.metadata["file_path"].replace(
                    self.config.CONTAINER_PATH,
                    self.config.LOCAL_FILES_PATH
                )
                links.add(f"file://{path}")
                results.append(item.page_content)

            output = {
                "links": links,
                "output": ". ".join(results)
            }
            
            logger.info(f"Found {len(found)} results")
            return output
            
        except Exception as e:
            logger.error(f"Search failed: {str(e)}")
            return {"error": "Unable to find anything for the given query"}

    def embed(self, query: str):
        return self.embed_model.embed_query(query)