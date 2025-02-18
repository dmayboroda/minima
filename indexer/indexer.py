import os
import uuid
import torch
import logging
import time
from dataclasses import dataclass
from typing import List, Dict
from pathlib import Path
from collections import defaultdict

from qdrant_client import QdrantClient
from langchain_qdrant import QdrantVectorStore
from langchain_huggingface import HuggingFaceEmbeddings
from qdrant_client.http.models import Distance, VectorParams, Filter, FieldCondition, MatchValue
from langchain.text_splitter import RecursiveCharacterTextSplitter

from langchain_community.document_loaders import (
    TextLoader,
    CSVLoader,
    Docx2txtLoader,
    UnstructuredExcelLoader,
    UnstructuredMarkdownLoader,
    BSHTMLLoader,
    PyMuPDFLoader,
    UnstructuredPowerPointLoader,
)

from storage import MinimaStore, IndexingStatus

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
        ".html": BSHTMLLoader,
        ".htm": BSHTMLLoader,
        ".md": UnstructuredMarkdownLoader,
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
    quadrant_collection_name = LOCAL_FILES_PATH.replace("/", "_").replace(":", "_").replace(".", "_").replace(" ", "_")
    QDRANT_COLLECTION = os.environ.get("QDRANT_COLLECTION", quadrant_collection_name)
    QDRANT_BOOTSTRAP = "qdrant"
    EMBEDDING_MODEL_ID = os.environ.get("EMBEDDING_MODEL_ID")
    EMBEDDING_SIZE = os.environ.get("EMBEDDING_SIZE")
    
    CHUNK_SIZE = 512
    CHUNK_OVERLAP = 50
    TOP_K = 20
    SCORE_THRESHOLD = 0.5

class StorageDict(defaultdict):
    def __missing__(self, key):
        if self.default_factory:
            dict.__setitem__(self, key, self.default_factory(key))
            return self[key]
        else:
            defaultdict.__missing__(self, key)

class Indexer:
    def __init__(self):
        self.config = Config()
        self.qdrant = self._initialize_qdrant()
        self.embed_model = self._initialize_embeddings()
        #self.document_store = self._setup_collection()
        self.document_stores = StorageDict(lambda x: self._setup_collection(x))
        #self.document_stores[self.config.QDRANT_COLLECTION] = self._setup_collection(self.config.QDRANT_COLLECTION)
        self.text_splitter = self._initialize_text_splitter()

    def _initialize_qdrant(self) -> QdrantClient:
        return QdrantClient(host=self.config.QDRANT_BOOTSTRAP)

    def _initialize_embeddings(self) -> HuggingFaceEmbeddings:
        return HuggingFaceEmbeddings(
            model_name=self.config.EMBEDDING_MODEL_ID,
            model_kwargs={'device': self.config.DEVICE, 'trust_remote_code': True},
            encode_kwargs={'normalize_embeddings': False}            
        )

    def _initialize_text_splitter(self) -> RecursiveCharacterTextSplitter:
        return RecursiveCharacterTextSplitter(
            chunk_size=self.config.CHUNK_SIZE,
            chunk_overlap=self.config.CHUNK_OVERLAP
        )

    def _setup_collection(self, pool_name: str) -> QdrantVectorStore:

        logger.info(f"*** Setting up collection: {pool_name}")
        if not self.qdrant.collection_exists(pool_name):
            self.qdrant.create_collection(
                collection_name=pool_name,
                vectors_config=VectorParams(
                    size=self.config.EMBEDDING_SIZE,
                    distance=Distance.COSINE
                ),
            )
        self.qdrant.create_payload_index(
            collection_name=pool_name,
            field_name="metadata.file_path",
            field_schema="keyword"
        )
        return QdrantVectorStore(
            client=self.qdrant,
            collection_name=pool_name,
            embedding=self.embed_model,
        )

    def _create_loader(self, file_path: str):
        file_extension = Path(file_path).suffix.lower()
        loader_class = self.config.EXTENSIONS_TO_LOADERS.get(file_extension)
        
        if not loader_class:
            raise ValueError(f"Unsupported file type: {file_extension}")
        
        return loader_class(file_path=file_path)

    def _poolname_from_file_path(self, file_path: str) -> str:
        # the poolname is derived from the first directory name in the file path

        try: 
            clean_pn = file_path[len(self.config.CONTAINER_PATH):].lstrip("/")
            if '/' in clean_pn:
                pn = clean_pn.split("/")[0]
            else:
                pn = 'default'
            if pn == "" or pn == None:
                return 'default'
            return pn
        except Exception as e:
            logger.warning(f"Error getting poolname from file path: {str(e)}")
            return 'default'

    def _process_file(self, loader) -> List[str]:
        try:
            documents = loader.load_and_split(self.text_splitter)
            if not documents:
                logger.warning(f"No documents loaded from {loader.file_path}")
                return []

            for doc in documents:
                doc.metadata['file_path'] = loader.file_path

            poolname = self._poolname_from_file_path(loader.file_path)
            uuids = [str(uuid.uuid4()) for _ in range(len(documents))]
            ids = self.document_stores[poolname].add_documents(documents=documents, ids=uuids)
            
            logger.info(f"Successfully processed {len(ids)} documents from {loader.file_path} for pool {poolname}")
            return ids
            
        except Exception as e:
            logger.error(f"Error processing file {loader.file_path}: {str(e)}")
            return []

    def index(self, message: Dict[str, any]) -> None:
        start = time.time()
        path, file_id, last_updated_seconds = message["path"], message["file_id"], message["last_updated_seconds"]
        logger.info(f"Processing file: {path} (ID: {file_id})")
        poolname = self._poolname_from_file_path(path)
        _ = self.document_stores[poolname]
        indexing_status: IndexingStatus = MinimaStore.check_needs_indexing(fpath=path, last_updated_seconds=last_updated_seconds)
        if indexing_status != IndexingStatus.no_need_reindexing:
            logger.info(f"Indexing needed for {path} with status: {indexing_status}")
            try:
                if indexing_status == IndexingStatus.need_reindexing:
                    logger.info(f"Removing {path} from index storage for reindexing")
                    try:
                        self.remove_from_storage(files_to_remove=[path])
                    except Exception as e:
                        logger.warning(f"Failed to remove {path} from storage: {str(e)}, continuing with reindexing")
                loader = self._create_loader(path)
                ids = self._process_file(loader)
                if ids:
                    logger.info(f"Successfully indexed {path} with {len(ids)} IDs.")
            except Exception as e:
                logger.error(f"Failed to index file {path}: {str(e)}")
        else:
            logger.info(f"Skipping {path}, no indexing required. timestamp didn't change")
        end = time.time()
        logger.info(f"Processing took {end - start} seconds for file {path}")

    def purge(self, message: Dict[str, any]) -> None:
        existing_file_paths: list[str] = message["existing_file_paths"]
        files_to_remove = MinimaStore.find_removed_files(existing_file_paths=set(existing_file_paths))
        if len(files_to_remove) > 0:
            logger.info(f"purge processing removing old files {files_to_remove}")
            self.remove_from_storage(files_to_remove)
        else:
            logger.info("Nothing to purge")

    def remove_from_storage(self, files_to_remove: list[str]):
        for poolname in self.document_stores.keys():
            logger.info(f"Removing files from storage for pool: {poolname}")

            pool_files_to_remove = [fpath for fpath in files_to_remove if self._poolname_from_file_path(fpath) == poolname]
            if pool_files_to_remove:
                filter_conditions = Filter(
                    must=[
                        FieldCondition(
                            key="metadata.file_path", 
                            match=MatchValue(value=fpath)
                        )
                        for fpath in pool_files_to_remove
                    ]
                )
                logger.debug(f" Filter for removing files from storage for pool {poolname}: {filter_conditions}")
                response = self.qdrant.delete(
                    collection_name=poolname,
                    points_selector=filter_conditions,
                    wait=True
                )
                logger.info(f"Delete response for {len(files_to_remove)} files is: {response}")

    def find(self, pool: str, query: str) -> Dict[str, any]: 
        if pool not in self.document_stores:
            if self.qdrant.collection_exists(pool):
                _ = self.document_stores[pool]
            else:
                logger.error(f"Unable to find anything for the given query in pool {pool}. The pool does not exist.")
                return {"error": f"Unable to find anything for the given query in pool {pool}. The pool does not exist."}

        try:
            logger.info(f"Searching for: {query}")
            found = self.document_stores[pool].search(query, search_type="similarity", k=self.config.TOP_K, score_threshold=self.config.SCORE_THRESHOLD)
            
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
                "output": ".\n\n\n ".join(results)
            }
            
            logger.info(f"Found {len(found)} results")
            return output
            
        except Exception as e:
            logger.error(f"Search failed: {str(e)}")
            return {"error": "Unable to find anything for the given query in pool {pool}"}

    def embed(self, query: str):
        return self.embed_model.embed_query(query)