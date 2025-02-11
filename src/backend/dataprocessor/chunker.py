import logging
from typing import List, Dict, Union
import tiktoken
from omegaconf import DictConfig
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document

logger = logging.getLogger(__name__)


class Chunker:
    def __init__(
        self,
        token_threshold: int,
        chunk_size: int,
        chunk_overlap: int
    ):
        self.token_threshold = token_threshold
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.encoders = {}  # Cache for encoders
    
    def _tokenizer(self, model: str) -> tiktoken.Encoding:
        """Get or create a token encoder for the specified model."""
        if model not in self.encoders:
            try:
                self.encoders[model] = tiktoken.encoding_for_model(model)
            except KeyError:
                self.encoders[model] = tiktoken.get_encoding("cl100k_base")
        return self.encoders[model]

    @property
    def text_splitter(self):
        """Lazy initialization of text splitter."""
        if not hasattr(self, '_text_splitter'):
            self._text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
                length_function=len,
                separators=[
                    "\n\n", "\n",
                    "。", "！", "？",  # Chinese
                    ". ", "! ", "? ",  # English
                    "；", "：", "，", "、",  # Chinese
                    "; ", ": ", ", ",  # English
                    "\u200b", "\uff0c", "\u3001", "\uff0e", "\u3002",  # Special characters
                    " ", ""
                ],
                keep_separator=True
            )
        return self._text_splitter

    def _get_token_count(self, text: str, model: str) -> int:
        """Count tokens in a text using tiktoken."""
        if not isinstance(text, str):
            text = str(text)
        
        # Clean the text
        text = text.replace('\n', ' ')  # Replace newlines with spaces
        text = ' '.join(text.split())   # Normalize whitespace
        
        try:
            encoder = self._tokenizer(model)
            return len(encoder.encode(text))
        except Exception as e:
            print(f"Error encoding text: {str(e)}")
            # You might want to log this error
            # Return a default value or raise the exception
            raise
    
    def _chunk_single_doc(
        self,
        text: str,
        model: str,
        metadata: Dict = None
    ) -> Dict:
        """
        Process a document based on its token count.
        If token count > threshold: chunk and create embeddings
        If token count <= threshold: save document directly without embedding
        """
        if not isinstance(text, str):
            text = str(text)
        
        # Clean the text before processing
        text = text.replace('\n', ' ')  # Replace newlines with spaces
        text = ' '.join(text.split())   # Normalize whitespace

        if metadata is None:
            metadata = {}

        token_count = self._get_token_count(text, model)
        total_characters = len(text)

        if token_count <= self.token_threshold:
            # Small documents: store as-is for direct LLM search
            full_text_info = {
                'type': 'full',
                'content': text,
                'metadata': metadata,
                'total_tokens': token_count,
                'total_characters': total_characters
            }
            logger.info(f"Document stored as full text, {token_count} tokens")
            logger.info(f"Total characters: {total_characters}")
            return full_text_info
        else:
            # Large documents: chunk using LangChain's splitter
            # Create a LangChain Document to use with the splitter
            doc = Document(page_content=text, metadata=metadata)
            chunks = self.text_splitter.split_documents([doc])

            # Log chunk details
            logger.info(f"Document chunked into {len(chunks)} pieces")
             # Log first chunk details
            if chunks:
                first_chunk = chunks[0].page_content
                first_chunk_chars = len(first_chunk)
                first_chunk_tokens = self._get_token_count(first_chunk, model)
                logger.info(f"First chunk: {first_chunk_tokens} tokens,"
                            f"{first_chunk_chars} characters")

            return {
                'type': 'chunked',
                'chunks': [{
                    'content': chunk.page_content,
                    'metadata': chunk.metadata
                } for chunk in chunks],
                'num_chunks': len(chunks)
            }


def batch_chunk_doc(
    cfg: DictConfig,
    documents: List[Union[str, Dict]]
) -> List[Dict]:
    """Process multiple documents."""
    chunker = Chunker(
        token_threshold=cfg.chunker.token_threshold,
        chunk_size=cfg.chunker.chunk_size,
        chunk_overlap=cfg.chunker.chunk_overlap
    )
    chunked_doc = []
    for doc in documents:
        if isinstance(doc, dict):
            text = doc['content']
            metadata = doc.get('metadata', {})
        else:
            text = doc
            metadata = {}
        chunked_doc.append(chunker._chunk_single_doc(
                                        text,
                                        cfg.llm.model,
                                        metadata
                                        ))
    logger.info(f"Processed {len(chunked_doc)} documents.")
    return chunked_doc
