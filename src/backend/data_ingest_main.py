"""To run in terminal: python -m src.backend.data_ingest_main"""
import logging
import hydra
from omegaconf import DictConfig
from typing import List, Union
from src.backend.utils.logging import setup_logging
from src.backend.dataloaders.gdrive_loader import GoogleDriveLoader
from src.backend.dataloaders.local_doc_loader import load_local_doc
from src.backend.rag.chunker import batch_chunk_doc
from src.backend.rag.embedder import embed_doc


@hydra.main(
    version_base=None,
    config_path="../../config",
    config_name="data_ingest")
def main(cfg: DictConfig) -> None:
    logger = logging.getLogger(__name__)
    logger.info("Setting up logging configuration.")
    setup_logging()
    
    all_documents = []
    # Load Google Drive documents if configured
    if hasattr(cfg, 'GDRIVE_DOC') and cfg.GDRIVE_DOC:
        logger.info("Loading Google Drive documents...")
        try:
            gdrive_loader = GoogleDriveLoader(
                credentials_path=cfg.GDRIVE.CREDENTIALS_PATH,
            )
            gdrive_docs = gdrive_loader.load_documents(cfg)
            all_documents.extend(gdrive_docs)
            logger.info(f"Loaded {len(gdrive_docs)} Google Drive documents.")
            
            # Log sample of document contents
            for i, doc in enumerate(gdrive_docs):
                logger.info(f"\nDocument {i+1} metadata:")
                logger.info(f"Type: {doc.doc_type}")
                logger.info(f"Filename: {doc.metadata.get('filename')}")
                
                # Log first 200 characters of content
                content_preview = doc.content[:200] if doc.content else "No content"
                logger.info(f"Content preview: {content_preview}...")
                
                if doc.doc_type == 'sheet':
                    logger.info(f"Sheet name: {doc.metadata.get('sheet_name')}")
                    logger.info(f"Number of rows: {doc.metadata.get('row_count')}")
                    logger.info(f"Columns: {doc.metadata.get('columns')}")
                
                logger.info("-" * 80)  # Separator line

        except Exception as e:
            logger.error(f"Error initializing Google Drive loader: {str(e)}")

    # Load local documents if configured
    if hasattr(cfg, 'LOCAL_DOC') and cfg.LOCAL_DOC:
        logger.info("Loading local documents...")
        try:
            local_docs = load_local_doc(cfg)
            all_documents.extend(local_docs)
            logger.info(f"Loaded {len(local_docs)} local documents.")
            
            # Log sample of local document contents
            for i, doc in enumerate(local_docs):
                logger.info(f"\nLocal Document {i+1} metadata:")
                logger.info(f"Filename: {doc.metadata.get('filename')}")
                
                # Log first 200 characters of content
                if hasattr(doc, 'content'):
                    content_preview = doc.content[:200] if doc.content else "No content"
                    logger.info(f"Content preview: {content_preview}...")
                
                # Log additional metadata
                for key, value in doc.metadata.items():
                    if key != 'filename':  # Already logged above
                        logger.info(f"{key}: {value}")
                
                logger.info("-" * 80)  # Separator line
                
        except Exception as e:
            logger.error(f"Error loading local documents: {str(e)}")
    if not all_documents:
        logger.warning("No documents were loaded. Please check your configuration.")
    # Log final summary
    logger.info(f"Total documents loaded: {len(all_documents)}")
    logger.info("Document loading pipeline completed.")

    # Chunker
    chunked_doc = batch_chunk_doc(cfg, all_documents)
    
    # Embedder
    try:
        embed_doc(cfg, chunked_doc)
    except Exception as e:
        logger.error(f"Error during document embedding: {str(e)}")

    return None


if __name__ == "__main__":
    main()
