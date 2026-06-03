"""Vector store sub-package — re-exports VectorStore, init_vector_store, and get_vector_store."""
from src.ai.vector_store_pkg.store import VectorStore, init_vector_store, get_vector_store

__all__ = ["VectorStore", "init_vector_store", "get_vector_store"]
