import operator
from typing import Optional, Sequence

from langchain_core.callbacks import Callbacks
from fastembed.rerank.cross_encoder import TextCrossEncoder
from langchain_core.documents import BaseDocumentCompressor, Document

class MinimaReranker(BaseDocumentCompressor):

    top_n: int = 3

    def __init__(
            self, model_name: str, 
            cache_dir: Optional[str] = None, 
            threads: Optional[int] = None, 
            **kwargs
    ):
        super().__init__(model_name, cache_dir, threads, **kwargs)
        self.model = TextCrossEncoder(model_name, cache_dir, threads)

    def compress_documents(
        self,
        documents: Sequence[Document],
        query: str,
        callbacks: Optional[Callbacks] = None,
    ) -> Sequence[Document]:
        scores = self.model.rerank(query, [doc.page_content for doc in documents])
        docs_with_scores = list(zip(documents, scores))
        result = sorted(docs_with_scores, key=operator.itemgetter(1), reverse=True)
        return [doc for doc, _ in result[: self.top_n]]