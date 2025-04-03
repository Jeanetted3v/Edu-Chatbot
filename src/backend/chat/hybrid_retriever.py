from typing import List, Dict, Any
import json
from pydantic import BaseModel
import chromadb
from chromadb.config import Settings
import chromadb.utils.embedding_functions as embedding_functions
from rank_bm25 import BM25Okapi
from utils.settings import SETTINGS


class SearchResult(BaseModel):
    content: str
    score: float
    metadata: Dict[str, Any]


class HybridRetriever:
    def __init__(self, cfg: Dict):
        self.cfg = cfg
        self.client = chromadb.PersistentClient(
            path=self.cfg.hybrid_retriever.persist_dir,
            settings=Settings(anonymized_telemetry=False)
        )
        self.embedding_function = embedding_functions.OpenAIEmbeddingFunction(
            api_key=SETTINGS.OPENAI_API_KEY,
            model_name=self.cfg.llm.embedding_model
        )
        self.collection = self.client.get_collection(
            name=self.cfg.hybrid_retriever.collection,
            embedding_function=self.embedding_function
        )
        
    def _normalize_scores(self, scores: List[float]) -> List[float]:
        """Min-max normalization of scores"""
        if not scores:
            return scores
        min_score = min(scores)
        max_score = max(scores)
        if max_score == min_score:
            return [1.0] * len(scores)
        return [(s - min_score) / (max_score - min_score) for s in scores]

    def _get_keyword_scores(
        self,
        query: str,
        documents: List[str]
    ) -> List[float]:
        """Get BM25 scores for keyword matching
        
        BM25 calculates a score based on Term Frequency 
        (how often words appear in the document), normalized longer documents,
        inverses document frequency (how common words are across documents). 
        Similar to TD-IDF + length normilization, etc. 
        """
        # Tokenize documents
        tokenized_docs = [doc.lower().split() for doc in documents]
        # Create BM25 index from tokenized documents
        bm25 = BM25Okapi(tokenized_docs)
        
        # Get keyword scores
        tokenized_query = query.lower().split()
        # Get BM25 scores for how well the query matches each document
        keyword_scores = bm25.get_scores(tokenized_query)
        # 0-1 normalize scores
        return self._normalize_scores(keyword_scores.tolist())

    async def search(
        self,
        query: str,
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
            n_results=self.cfg.hybrid_retriever.top_k,
            where=filter_conditions,
            include=['documents', 'metadatas', 'distances']
        )
        
        # Accessing the inner lists of results. Chromadb supports batch queries
        documents = results['documents'][0]
        metadatas = results['metadatas'][0]
        # Convert distances to similarity scores (1 - distance)
        semantic_scores = self._normalize_scores(
            [1 - d for d in results['distances'][0]]
        )
        
        # Get keyword search scores
        keyword_scores = self._get_keyword_scores(query, documents)
        
        # Combine scores
        combined_scores = [
            (self.cfg.hybrid_retriever.semantic_weight * ss + self.cfg.hybrid_retriever.keyword_weight * ks)
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
    
    def format_search_results(
        self, search_results: List[SearchResult]
    ) -> tuple:
        """Format search results for inclusion in prompt context"""
        formatted_results = []
        top_result = None
        max_score = float('-inf')

        for result in search_results:
            formatted_result = {
                'content': result.content,
                'relevance_score': f"{result.score:.2f}",
                'metadata': {
                    'category': result.metadata.get('category', ''),
                    'keywords': result.metadata.get('keywords', []),
                    'related_topics': result.metadata.get('related_topics', [])
                }
            }
            formatted_results.append(formatted_result)
        if result.score > max_score:
            max_score = result.score
            top_result = result.content
        
        return json.dumps(formatted_results, indent=2), top_result