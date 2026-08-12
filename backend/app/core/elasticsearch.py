import logging
from typing import Any, Dict, List, Optional
from elasticsearch import Elasticsearch, ApiError
from app.core.config import settings

logger = logging.getLogger(__name__)


class ElasticsearchService:
    def __init__(self):
        self.client = Elasticsearch(settings.ELASTICSEARCH_HOST)

    def create_index(self, index_name: str, dims: int = 384) -> bool:
        """Create an Elasticsearch index with custom mappings for lexical and dense vector search."""
        mappings = {
            "mappings": {
                "properties": {
                    "document_id": {"type": "keyword"},
                    "title": {"type": "text", "analyzer": "standard"},
                    "content": {"type": "text", "analyzer": "standard"},
                    "clean_content": {"type": "text", "analyzer": "standard"},
                    "embedding": {
                        "type": "dense_vector",
                        "dims": dims,
                        "index": True,
                        "similarity": "cosine",
                    },
                }
            }
        }
        try:
            if not self.client.indices.exists(index=index_name):
                self.client.indices.create(index=index_name, body=mappings)
                logger.info(f"Created Elasticsearch index '{index_name}' successfully.")
                return True
            return False
        except ApiError as e:
            logger.error(f"Failed to create Elasticsearch index: {e}")
            raise RuntimeError(f"Elasticsearch index creation failed: {e}") from e

    def index_document(
        self,
        index_name: str,
        document_id: str,
        title: str,
        content: str,
        clean_content: str,
        embedding: List[float],
    ) -> Dict[str, Any]:
        """Index a document with its text fields and dense vector embeddings."""
        doc_body = {
            "document_id": document_id,
            "title": title,
            "content": content,
            "clean_content": clean_content,
            "embedding": embedding,
        }
        try:
            response = self.client.index(
                index=index_name, id=document_id, body=doc_body, refresh=True
            )
            return dict(response)
        except ApiError as e:
            logger.error(f"Failed to index document '{document_id}': {e}")
            raise RuntimeError(f"Elasticsearch indexing failed: {e}") from e

    def hybrid_search(
        self,
        index_name: str,
        query_text: str,
        query_vector: Optional[List[float]] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Perform a hybrid search combining lexical search (BM25) and Approximate Nearest Neighbor (ANN) embeddings.
        
        If a query_vector is supplied, we perform a hybrid search utilizing Elasticsearch's kNN query.
        """
        try:
            if not self.client.indices.exists(index=index_name):
                return []

            # Basic query matching the content or clean_content lexically
            query_body: Dict[str, Any] = {
                "size": limit,
                "query": {
                    "multi_match": {
                        "query": query_text,
                        "fields": ["title^2", "content", "clean_content"],
                    }
                },
            }

            # If vector embeddings are available, add a kNN parameter to enable ANN search
            if query_vector:
                query_body["knn"] = {
                    "field": "embedding",
                    "query_vector": query_vector,
                    "k": limit,
                    "num_candidates": 50,
                    "boost": 0.5,  # Weight balancing dense embeddings vs lexical search
                }
                # To perform a hybrid query where we combine BM25 and kNN scores,
                # we let both search methods contribute to the hits.
                # The boost factor adjusts the relative weights of lexical and dense scores.

            response = self.client.search(index=index_name, body=query_body)
            hits = response["hits"]["hits"]

            results = []
            for hit in hits:
                source = hit["_source"]
                results.append(
                    {
                        "document_id": source.get("document_id"),
                        "title": source.get("title"),
                        "score": hit["_score"],
                        "clean_content_snippet": source.get("clean_content", "")[:200] + "...",
                    }
                )
            return results

        except ApiError as e:
            logger.error(f"Elasticsearch search failed: {e}")
            raise RuntimeError(f"Elasticsearch search failed: {e}") from e


es_service = ElasticsearchService()
