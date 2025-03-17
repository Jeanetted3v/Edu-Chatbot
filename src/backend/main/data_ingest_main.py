"""To run in terminal: python -m src.backend.main.data_ingest_main"""
import logging
import hydra
import asyncio
from omegaconf import DictConfig
from src.backend.utils.logging import setup_logging
from src.backend.dataloaders.gdrive_loader import GoogleDriveLoader
from src.backend.dataloaders.local_doc_loader import load_local_doc
from src.backend.dataprocessor.chunker import batch_chunk_doc
from src.backend.dataprocessor.embedder import embed_doc


logger = logging.getLogger(__name__)
logger.info("Setting up logging configuration.")
setup_logging()


@hydra.main(
    version_base=None,
    config_path="../../../config",
    config_name="data_ingest")
def main(cfg: DictConfig) -> None:
    pdfs = []
    if hasattr(cfg, 'gdrive_doc') and cfg.gdrive_doc:
        try:
            gdrive_loader = GoogleDriveLoader(
                credentials_path=cfg.gdrive.credentials_path,
            )
            gdrive_docs = gdrive_loader.load_documents(cfg)
            pdfs.extend([
                doc for doc in gdrive_docs
                if hasattr(doc, 'doc_type') and doc.doc_type == 'pdf'
            ])
        except Exception as e:
            logger.error(f"Error initializing Google Drive loader: {str(e)}")

    if hasattr(cfg, 'local_doc') and cfg.local_doc:
        try:
            local_docs = load_local_doc(cfg)
            if local_docs:
                pdf_docs = [
                    doc for doc in local_docs
                    if hasattr(doc, 'metadata') and
                    doc.metadata.get('type') == 'pdf'
                ]
                pdfs.extend(pdf_docs)
                logger.info(f"Found {len(pdfs)} PDF files in local documents")
            else:
                logger.info("No local documents were loaded")
        except Exception as e:
            logger.error(f"Error loading local documents: {str(e)}")

    if pdfs:
        chunked_doc = batch_chunk_doc(cfg, pdfs)
        try:
            asyncio.run(embed_doc(cfg, chunked_doc))
        except Exception as e:
            logger.error(f"Error during document embedding: {str(e)}")
    return None


if __name__ == "__main__":
    main()
