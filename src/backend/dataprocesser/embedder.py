import logging
from typing import List, Dict, Optional
import uuid
from omegaconf import DictConfig
import chromadb
from chromadb.config import Settings
import chromadb.utils.embedding_functions as embedding_functions
from utils.settings import SETTINGS

logger = logging.getLogger(__name__)


class Embedder:
    def __init__(
        self,
        persist_directory: str
    ):
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(anonymized_telemetry=False)
        )
        self.collection = None

    def _create_embedding_function(
        self,
        provider: str,
        model_name: str,
        api_key: Optional[str] = None
    ) -> embedding_functions.EmbeddingFunction:
        if provider.lower() == "openai":
            return embedding_functions.OpenAIEmbeddingFunction(
                api_key=api_key,
                model_name=model_name
            )
        raise ValueError(f"Unsupported embedding provider: {provider}")

    def _create_collection(
        self,
        collection_name: str,
        similarity_metric: str,
        metadata: Optional[Dict] = None,
        embedding_function: Optional[embedding_functions.EmbeddingFunction] = None
    ):
        if metadata is None:
            metadata = {"hnsw:space": similarity_metric}
            
        return self.client.get_or_create_collection(
            name=collection_name,
            metadata=metadata,
            embedding_function=embedding_function
        )

    def _store_processed_documents(self, processed_docs: List[Dict]):
        """
        Store processed documents in ChromaDB.
        Handles both chunked and full documents appropriately.
        """
        for doc in processed_docs:
            if doc['type'] == 'chunked':
                # For chunked documents, store each chunk with its embedding
                # Use add method, upsert method might overwrite existing embeddings
                for chunk in doc['chunks']:
                    self.collection.add(
                        documents=[chunk['content'] for chunk in doc['chunks']],
                        metadatas=[{
                         **chunk['metadata'],
                         'chunk_type': 'partial',
                         'total_chunks': doc['num_chunks'],
                         'doc_id': doc.get('doc_id', str(uuid.uuid4()))
                        } for chunk in doc['chunks']],
                        ids=[str(uuid.uuid4()) for _ in doc['chunks']]
                    )
            else:
                # For full documents, store without embeddings
                # Use add_documents method which doesn't generate embeddings
                self.client.get_or_create_collection(
                    name=f"{self.collection.name}_full",  # Separate collection for full docs
                    metadata={"type": "full_documents"}
                ).add(
                    documents=[doc['content']],
                    metadatas=[{
                        **doc['metadata'],
                        'chunk_type': 'full',
                        'total_tokens': doc['total_tokens'],
                        'doc_id': doc.get('doc_id', str(uuid.uuid4()))
                    }],
                    ids=[str(uuid.uuid4())]
                )


def embed_doc(cfg: DictConfig, processed_docs: List[Dict]) -> None:
    logger.info("Starting document embedding process...")
    embedder = Embedder(cfg.EMBEDDER.PERSIST_DIR)
    embedding_fn = embedder._create_embedding_function(
        provider=cfg.LLM.PROVIDER,
        model_name=cfg.LLM.EMBEDDING_MODEL,
        api_key=SETTINGS.OPENAI_API_KEY
    )
    embedder.collection = embedder._create_collection(
        collection_name=cfg.EMBEDDER.COLLECTION_NAME,
        similarity_metric=cfg.EMBEDDER.SIMILARITY_METRIC,
        embedding_function=embedding_fn
    )

    total_chunks = sum(
        len(doc['chunks']) if doc['type'] == 'chunked' else 1
        for doc in processed_docs
    )
    logger.info(f"Processing {len(processed_docs)} documents"
                f"with total {total_chunks} chunks")
    try:
        embedder._store_processed_documents(processed_docs)
        
        # Verify embeddings by checking collection count
        collection_count = embedder.collection.count()
        logger.info(f"Successfully stored {collection_count}"
                    f"embeddings in collection")
        
        # Optional: Check a few random embeddings
        if collection_count > 0:
            sample = embedder.collection.get(limit=1)
            if sample and 'embeddings' in sample:
                logger.info("Sample embedding verification successful")
            else:
                logger.warning("Sample embedding verification failed")              
    except Exception as e:
        logger.error(f"Error during document embedding: {str(e)}")
        raise e
    logger.info("Document embedding process completed")
    return None