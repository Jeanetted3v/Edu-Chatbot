from typing import List, Optional, Dict, Any
import chromadb
from uuid import uuid4


class ChromaDBUtils:
    def __init__(self, collection: chromadb.Collection):
        """
        Initialize ChromaDB utilities with a collection.
        
        Args:
            collection (chromadb.Collection): ChromaDB collection instance
        """
        self.collection = collection

    def upsert_documents(
        self,
        documents: List[str],
        ids: Optional[List[str]] = None,
        metadatas: Optional[List[Dict[str, Any]]] = None,
        embeddings: Optional[List[List[float]]] = None
    ):
        """
        Upsert documents into the collection.
        
        Args:
            documents (List[str]): List of document texts
            ids (List[str], optional): List of IDs for the documents
            metadatas (List[Dict], optional): List of metadata dicts for each document
            embeddings (List[List[float]], optional): Pre-computed embeddings
        """
        if ids is None:
            ids = [str(uuid4()) for _ in documents]
            
        try:
            self.collection.upsert(
                documents=documents,
                ids=ids,
                metadatas=metadatas,
                embeddings=embeddings
            )
        except Exception as e:
            raise Exception(f"Failed to upsert documents: {str(e)}")

    def delete_documents(self, ids: List[str]):
        """
        Delete documents from the collection by their IDs.
        
        Args:
            ids (List[str]): List of document IDs to delete
        """
        try:
            self.collection.delete(ids=ids)
        except Exception as e:
            raise Exception(f"Failed to delete documents: {str(e)}")

    def query_documents(
        self,
        query_texts: List[str],
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None,
        where_document: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Query the collection for similar documents.
        
        Args:
            query_texts (List[str]): List of query texts
            n_results (int): Number of results to return
            where (Dict, optional): Metadata filters
            where_document (Dict, optional): Document content filters
            
        Returns:
            Dict: Query results containing documents, distances, and metadata
        """
        try:
            results = self.collection.query(
                query_texts=query_texts,
                n_results=n_results,
                where=where,
                where_document=where_document
            )
            return results
        except Exception as e:
            raise Exception(f"Failed to query documents: {str(e)}")

    def get_document_by_id(self, id: str) -> Dict[str, Any]:
        """
        Retrieve a specific document by its ID.
        
        Args:
            id (str): Document ID
            
        Returns:
            Dict: Document data including content and metadata
        """
        try:
            return self.collection.get(ids=[id])
        except Exception as e:
            raise Exception(f"Failed to get document: {str(e)}")

    def count_documents(self) -> int:
        """
        Get the total number of documents in the collection.
        
        Returns:
            int: Number of documents
        """
        try:
            return self.collection.count()
        except Exception as e:
            raise Exception(f"Failed to count documents: {str(e)}")


if __name__ == "__main__":
    # Example usage
    from init_chromadb import init_chromadb, get_or_create_collection
    
    # Initialize ChromaDB and collection
    client = init_chromadb()
    collection = get_or_create_collection(client, "test_collection")
    
    # Initialize utils
    db_utils = ChromaDBUtils(collection)
    
    # Example documents
    test_docs = [
        "This is a test document about AI",
        "This is another document about machine learning"
    ]
    
    # Upsert documents
    db_utils.upsert_documents(
        documents=test_docs,
        metadatas=[{"source": "test"} for _ in test_docs]
    )
    
    # Query documents
    results = db_utils.query_documents(
        query_texts=["Tell me about AI"],
        n_results=2
    )
    print("Query results:", results)