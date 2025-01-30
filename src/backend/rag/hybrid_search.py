# searcher.py
import chromadb
from typing import Dict, Optional, List


class Searcher:
    def __init__(
        self,
        persist_directory: str = "./data/embeddings",
        collection_name: str = "document_embeddings"
    ):
        self.client = chromadb.PersistentClient(path=persist_directory)
        # Get both collections
        self.chunk_collection = self.client.get_collection(f"{collection_name}")
        self.full_collection = self.client.get_collection(f"{collection_name}_full")

    def hybrid_search(
        self,
        query: str,
        filter_dict: Optional[Dict] = None,
        n_results: int = 5,
        embedding_weight: float = 0.7
    ) -> Dict:
        """
        Hybrid search using both semantic similarity and keyword matching.
        Only searches through chunked documents.
        """
        # Get dense embedding results (semantic search)
        dense_results = self.chunk_collection.query(
            query_texts=[query],
            where=filter_dict,
            n_results=n_results,
            include=["documents", "metadatas", "distances"]
        )
        
        # Get keyword matching results
        keyword_results = self.chunk_collection.query(
            query_texts=[query],
            where=filter_dict,
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
            search_type="keywords"
        )
        
        # Combine and rank results
        return self._combine_search_results(
            dense_results, 
            keyword_results, 
            embedding_weight
        )

    def full_text_search(
        self,
        query: str,
        filter_dict: Optional[Dict] = None,
        n_results: int = 5
    ) -> Dict:
        """
        Search through full documents using keyword matching.
        """
        return self.full_collection.query(
            query_texts=[query],
            where=filter_dict,
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
            search_type="keywords"  # Use keyword search for full docs
        )

    def _combine_search_results(
        self,
        dense_results: Dict,
        keyword_results: Dict,
        embedding_weight: float
    ) -> Dict:
        """
        Combine and re-rank dense and keyword search results.
        """
        combined = {}
        
        # Process dense results
        if 'documents' in dense_results and dense_results['documents']:
            for doc, meta, dist in zip(
                dense_results['documents'][0],
                dense_results['metadatas'][0],
                dense_results['distances'][0]
            ):
                doc_id = meta['doc_id']
                combined[doc_id] = {
                    'content': doc,
                    'metadata': meta,
                    'score': dist * embedding_weight
                }
        
        # Process keyword results
        if 'documents' in keyword_results and keyword_results['documents']:
            for doc, meta, dist in zip(
                keyword_results['documents'][0],
                keyword_results['metadatas'][0],
                keyword_results['distances'][0]
            ):
                doc_id = meta['doc_id']
                if doc_id in combined:
                    combined[doc_id]['score'] += dist * (1 - embedding_weight)
                else:
                    combined[doc_id] = {
                        'content': doc,
                        'metadata': meta,
                        'score': dist * (1 - embedding_weight)
                    }
        
        # Sort by combined score
        sorted_results = sorted(
            combined.values(),
            key=lambda x: x['score'],
            reverse=True
        )
        
        return {
            'documents': [r['content'] for r in sorted_results],
            'metadatas': [r['metadata'] for r in sorted_results],
            'distances': [r['score'] for r in sorted_results]
        }

    def search_all(
        self,
        query: str,
        n_results: int = 5,
        embedding_weight: float = 0.7
    ) -> Dict:
        """
        Search both full documents and chunks, combine results.
        """
        # Search chunks with hybrid search
        chunk_results = self.hybrid_search(
            query=query,
            n_results=n_results,
            embedding_weight=embedding_weight
        )
        
        # Search full documents with keyword matching
        full_results = self.full_text_search(
            query=query,
            n_results=n_results
        )
        
        # Combine results (you might want to customize this based on your needs)
        return {
            'documents': full_results['documents'][0] + chunk_results['documents'],
            'metadatas': full_results['metadatas'][0] + chunk_results['metadatas'],
            'distances': full_results['distances'][0] + chunk_results['distances']
        }