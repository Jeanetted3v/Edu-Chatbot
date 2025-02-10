from typing import List, Dict, Any
from pydantic import BaseModel
import chromadb
from rank_bm25 import BM25Okapi
import numpy as np


class SearchResult(BaseModel):
    content: str
    score: float
    metadata: Dict[str, Any]


class HybridSearch:
    def __init__(self, collection_name: str, cfg):
        self.chroma_client = chromadb.Client()
        self.collection = self.chroma_client.get_collection(collection_name)
        self.cfg = cfg
        # Weights for combining scores
        self.semantic_weight = 0.7
        self.keyword_weight = 0.3
        
    def _normalize_scores(self, scores: List[float]) -> List[float]:
        """Min-max normalization of scores"""
        if not scores:
            return scores
        min_score = min(scores)
        max_score = max(scores)
        if max_score == min_score:
            return [1.0] * len(scores)
        return [(s - min_score) / (max_score - min_score) for s in scores]

    def _get_keyword_scores(self, query: str, documents: List[str]) -> List[float]:
        """Get BM25 scores for keyword matching"""
        # Tokenize documents
        tokenized_docs = [doc.lower().split() for doc in documents]
        bm25 = BM25Okapi(tokenized_docs)
        
        # Get keyword scores
        tokenized_query = query.lower().split()
        keyword_scores = bm25.get_scores(tokenized_query)
        return self._normalize_scores(keyword_scores.tolist())

    async def search(
        self, 
        query: str, 
        n_results: int = 5,
        filter_conditions: Dict = None
    ) -> List[SearchResult]:
        """
        Perform hybrid search combining semantic and keyword matching
        
        Args:
            query: Search query string
            n_results: Number of results to return
            filter_conditions: Optional filters for metadata fields
        """
        # Get semantic search results with scores
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results,
            where=filter_conditions,
            include=['documents', 'metadatas', 'distances']
        )
        
        documents = results['documents'][0]
        metadatas = results['metadatas'][0]
        semantic_scores = self._normalize_scores([1 - d for d in results['distances'][0]])
        
        # Get keyword search scores
        keyword_scores = self._get_keyword_scores(query, documents)
        
        # Combine scores
        combined_scores = [
            (self.semantic_weight * ss + self.keyword_weight * ks)
            for ss, ks in zip(semantic_scores, keyword_scores)
        ]
        
        # Sort results by combined score
        search_results = []
        for doc, meta, score in zip(documents, metadatas, combined_scores):
            search_results.append(
                SearchResult(
                    content=doc,
                    score=score,
                    metadata=meta
                )
            )
            
        return sorted(search_results, key=lambda x: x.score, reverse=True)