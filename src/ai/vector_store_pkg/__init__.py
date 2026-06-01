"""Vector store sub-package — re-exports public API."""
from src.ai.vector_store_pkg.store import VectorStore, init_vector_store, get_vector_store

__all__ = ["VectorStore", "init_vector_store", "get_vector_store"]
