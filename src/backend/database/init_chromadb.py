

import chromadb
from chromadb.config import Settings

def init_chromadb(persist_directory: str = "./chroma_db"):
    """
    Initialize ChromaDB client with persistence.
    
    Args:
        persist_directory (str): Directory where ChromaDB will store its data
        
    Returns:
        chromadb.Client: Initialized ChromaDB client
    """
    try:
        client = chromadb.Client(
            Settings(
                persist_directory=persist_directory,
                anonymized_telemetry=False
            )
        )
        return client
    except Exception as e:
        raise Exception(f"Failed to initialize ChromaDB: {str(e)}")

def get_or_create_collection(
    client: chromadb.Client,
    collection_name: str,
    metadata: dict = None
):
    """
    Get an existing collection or create a new one if it doesn't exist.
    
    Args:
        client (chromadb.Client): ChromaDB client instance
        collection_name (str): Name of the collection
        metadata (dict, optional): Metadata for the collection
        
    Returns:
        chromadb.Collection: ChromaDB collection
    """
    try:
        collection = client.get_or_create_collection(
            name=collection_name,
            metadata=metadata
        )
        return collection
    except Exception as e:
        raise Exception(f"Failed to get or create collection: {str(e)}")

if __name__ == "__main__":
    # Example usage
    client = init_chromadb()
    collection = get_or_create_collection(client, "my_collection")
    print("ChromaDB initialized successfully!")