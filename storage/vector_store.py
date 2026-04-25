import os
from pathlib import Path
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions

CHROMA_PATH = os.getenv("CHROMADB_PATH", "./data/chroma")

_client = None
_collection = None


def init_collection():
    """Initialize ChromaDB client and collection."""
    global _client, _collection
    
    # Ensure the directory exists
    chroma_dir = Path(CHROMA_PATH)
    chroma_dir.mkdir(parents=True, exist_ok=True)
    
    # Create persistent client
    _client = chromadb.PersistentClient(path=CHROMA_PATH)
    
    # Get or create collection with cosine similarity
    _collection = _client.get_or_create_collection(
        name="groww_reviews",
        metadata={"hnsw:space": "cosine"}
    )
    
    return _collection


def get_collection():
    """Get the ChromaDB collection, initializing if necessary."""
    global _collection
    if _collection is None:
        init_collection()
    return _collection


def upsert_embeddings(ids: List[str], embeddings: List[List[float]], metadatas: List[Dict[str, Any]]) -> bool:
    """Upsert embeddings into the ChromaDB collection."""
    try:
        collection = get_collection()
        
        # Validate inputs
        if not (len(ids) == len(embeddings) == len(metadatas)):
            raise ValueError("Length mismatch between ids, embeddings, and metadatas")
        
        # Upsert the data
        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas
        )
        return True
    except Exception as e:
        print(f"Error upserting embeddings: {e}")
        return False


def query_similar(embedding: List[float], n_results: int = 10, where: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Query for similar embeddings in the collection."""
    try:
        collection = get_collection()
        
        query_params = {
            "query_embeddings": [embedding],
            "n_results": n_results
        }
        
        if where:
            query_params["where"] = where
        
        results = collection.query(**query_params)
        return results
    except Exception as e:
        print(f"Error querying similar embeddings: {e}")
        return {"ids": [], "metadatas": [], "distances": [], "documents": []}


def get_by_ids(ids: List[str]) -> Dict[str, Any]:
    """Get documents by their IDs."""
    try:
        collection = get_collection()
        results = collection.get(ids=ids)
        return results
    except Exception as e:
        print(f"Error getting documents by IDs: {e}")
        return {"ids": [], "metadatas": [], "documents": []}


def delete_by_ids(ids: List[str]) -> bool:
    """Delete documents by their IDs."""
    try:
        collection = get_collection()
        collection.delete(ids=ids)
        return True
    except Exception as e:
        print(f"Error deleting documents by IDs: {e}")
        return False


def get_collection_stats() -> Dict[str, Any]:
    """Get statistics about the collection."""
    try:
        collection = get_collection()
        count = collection.count()
        return {
            "total_documents": count,
            "collection_name": collection.name,
            "path": CHROMA_PATH
        }
    except Exception as e:
        print(f"Error getting collection stats: {e}")
        return {}


def clear_collection() -> bool:
    """Clear all documents from the collection."""
    try:
        collection = get_collection()
        # Delete all documents by querying all IDs first
        all_docs = collection.get()
        if all_docs["ids"]:
            collection.delete(ids=all_docs["ids"])
        return True
    except Exception as e:
        print(f"Error clearing collection: {e}")
        return False
