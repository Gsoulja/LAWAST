"""
Embedding Generator for LAWAST

Generates semantic embeddings for legal text using multilingual-e5-large model.
Supports batch processing for efficient embedding generation.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import torch
from sentence_transformers import SentenceTransformer
from concurrent.futures import ThreadPoolExecutor, as_completed
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class EmbeddingBatch:
    texts: List[str]
    uris: List[str]
    node_types: List[str]


class EmbeddingGenerator:
    """
    Generates semantic embeddings for legal documents.

    Uses multilingual-e5-large model for multilingual support.
    Optimized for batch processing with GPU acceleration when available.
    """

    def __init__(self, model_name: str = "intfloat/multilingual-e5-large",
                 batch_size: int = 32, device: Optional[str] = None):
        """
        Initialize the embedding generator.

        Args:
            model_name: Hugging Face model identifier
            batch_size: Number of texts to process in parallel
            device: Device to use ('cuda', 'cpu', or None for auto)
        """
        self.model_name = model_name
        self.batch_size = batch_size

        if device is None:
            # Force CPU usage to avoid CUDA issues
            self.device = 'cpu'
            # Uncomment below to auto-detect (but currently CUDA is problematic)
            # self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        else:
            self.device = device

        logger.info(f"Loading embedding model: {model_name}")
        logger.info(f"Using device: {self.device}")

        self.model = SentenceTransformer(model_name, device=self.device)
        self.embedding_dim = self.model.get_sentence_embedding_dimension()

        logger.info(f"Model loaded. Embedding dimension: {self.embedding_dim}")

    def generate_embedding(self, text: str, prefix: str = "passage: ") -> List[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Input text
            prefix: Prefix for the text (e5 models use "passage: " or "query: ")

        Returns:
            Embedding vector as list of floats
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for embedding")
            return [0.0] * self.embedding_dim

        prefixed_text = prefix + text.strip()

        embedding = self.model.encode(
            prefixed_text,
            convert_to_numpy=True,
            normalize_embeddings=True
        )

        return embedding.tolist()

    def generate_embeddings_batch(self, texts: List[str],
                                  prefix: str = "passage: ") -> List[List[float]]:
        """
        Generate embeddings for multiple texts in batch.

        Args:
            texts: List of input texts
            prefix: Prefix for texts

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        prefixed_texts = [prefix + (text.strip() if text else "") for text in texts]

        embeddings = self.model.encode(
            prefixed_texts,
            batch_size=self.batch_size,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=len(texts) > 100
        )

        return embeddings.tolist()

    def generate_law_embedding(self, law_data: Dict[str, Any]) -> List[float]:
        """
        Generate embedding for a law node.

        Combines title and description for better semantic representation.

        Args:
            law_data: Dictionary with 'title' and optionally 'short_title'

        Returns:
            Embedding vector
        """
        text_parts = []

        if law_data.get('title'):
            text_parts.append(law_data['title'])

        if law_data.get('short_title'):
            text_parts.append(law_data['short_title'])

        combined_text = " - ".join(text_parts) if text_parts else ""

        return self.generate_embedding(combined_text)

    def generate_article_embedding(self, article_data: Dict[str, Any]) -> List[float]:
        """
        Generate embedding for an article node.

        Uses title and content_preview if available, otherwise full content.

        Args:
            article_data: Dictionary with 'title', 'content_preview', or 'content_full'

        Returns:
            Embedding vector
        """
        text_parts = []

        if article_data.get('title'):
            text_parts.append(article_data['title'])

        if article_data.get('content_preview'):
            text_parts.append(article_data['content_preview'])
        elif article_data.get('content_full'):
            preview = article_data['content_full'][:500]
            text_parts.append(preview)

        combined_text = " - ".join(text_parts) if text_parts else ""

        return self.generate_embedding(combined_text)

    def generate_paragraph_embedding(self, paragraph_data: Dict[str, Any]) -> List[float]:
        """
        Generate embedding for a paragraph node.

        Args:
            paragraph_data: Dictionary with 'text'

        Returns:
            Embedding vector
        """
        text = paragraph_data.get('text', '')
        return self.generate_embedding(text)

    def generate_subpoint_embedding(self, subpoint_data: Dict[str, Any]) -> List[float]:
        """
        Generate embedding for a subpoint node.

        Args:
            subpoint_data: Dictionary with 'text'

        Returns:
            Embedding vector
        """
        text = subpoint_data.get('text', '')
        return self.generate_embedding(text)

    def process_batch(self, batch: EmbeddingBatch) -> List[Tuple[str, List[float]]]:
        """
        Process a batch of mixed node types.

        Args:
            batch: EmbeddingBatch with texts, URIs, and node types

        Returns:
            List of (uri, embedding) tuples
        """
        embeddings = self.generate_embeddings_batch(batch.texts)

        results = []
        for uri, embedding in zip(batch.uris, embeddings):
            results.append((uri, embedding))

        return results

    def create_vector_indexes(self, graph_builder) -> None:
        """
        Create vector indexes in Neo4j for efficient similarity search.

        Args:
            graph_builder: GraphBuilder instance
        """
        logger.info("Creating vector indexes for embeddings...")

        indexes = [
            ("law_embedding_index", "Law", "embedding"),
            ("article_embedding_index", "Article", "embedding"),
            ("paragraph_embedding_index", "Paragraph", "embedding"),
            ("subpoint_embedding_index", "Subpoint", "embedding")
        ]

        for index_name, label, property_name in indexes:
            query = f"""
            CREATE VECTOR INDEX {index_name} IF NOT EXISTS
            FOR (n:{label})
            ON n.{property_name}
            OPTIONS {{
                indexConfig: {{
                    `vector.dimensions`: {self.embedding_dim},
                    `vector.similarity_function`: 'cosine'
                }}
            }}
            """

            try:
                graph_builder.connection.execute_write(query)
                logger.info(f"Created vector index: {index_name}")
            except Exception as e:
                logger.warning(f"Vector index {index_name} may already exist: {e}")

    def similarity_search(self, graph_builder, query_text: str,
                         node_label: str = "Article", top_k: int = 10) -> List[Dict[str, Any]]:
        """
        Perform similarity search using vector index.

        Args:
            graph_builder: GraphBuilder instance
            query_text: Query text to search for
            node_label: Node label to search in
            top_k: Number of results to return

        Returns:
            List of matching nodes with similarity scores
        """
        query_embedding = self.generate_embedding(query_text, prefix="query: ")

        cypher_query = f"""
        CALL db.index.vector.queryNodes('{node_label.lower()}_embedding_index', $top_k, $query_vector)
        YIELD node, score
        RETURN node, score
        ORDER BY score DESC
        """

        params = {
            "query_vector": query_embedding,
            "top_k": top_k
        }

        results = graph_builder.connection.execute_read(cypher_query, params)
        return results

    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the loaded model"""
        return {
            "model_name": self.model_name,
            "embedding_dim": self.embedding_dim,
            "device": self.device,
            "batch_size": self.batch_size
        }


def create_embedding_generator(batch_size: int = 32, device: str = 'cpu') -> EmbeddingGenerator:
    """
    Convenience function to create an embedding generator.

    Args:
        batch_size: Batch size for processing
        device: Device to use ('cpu' or 'cuda'), defaults to 'cpu'

    Returns:
        Configured EmbeddingGenerator instance
    """
    return EmbeddingGenerator(
        model_name="intfloat/multilingual-e5-large",
        batch_size=batch_size,
        device=device  # Explicitly pass device, defaulting to CPU
    )