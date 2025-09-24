"""Simple Vector RAG for quick start"""

from sentence_transformers import SentenceTransformer
import numpy as np
from typing import List, Tuple

class SimpleVectorRAG:
    def __init__(self):
        self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
        self.documents = []
        self.embeddings = []

    def index_documents(self, documents: List[dict]):
        """Index documents for retrieval"""
        self.documents = documents
        texts = [doc.get('content', '') for doc in documents]
        self.embeddings = self.embedder.encode(texts)
        print(f"Indexed {len(documents)} documents")

    def search(self, query: str, k: int = 5) -> List[dict]:
        """Search for relevant documents"""
        if not self.documents:
            return []

        query_embedding = self.embedder.encode([query])[0]

        # Compute similarities
        similarities = np.dot(self.embeddings, query_embedding)
        top_k = np.argsort(similarities)[::-1][:k]

        return [self.documents[i] for i in top_k]
