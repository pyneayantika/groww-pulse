import numpy as np
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any, Tuple
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from storage.vector_store import upsert_embeddings

PRIMARY_MODEL = "BAAI/bge-small-en-v1.5"      # 384-dim, free, local
SECONDARY_MODEL = "all-MiniLM-L6-v2"             # 384-dim, faster, lighter
TERTIARY_MODEL = "paraphrase-MiniLM-L3-v2"      # 384-dim, smallest/fastest

_model = None  # lazy singleton
_model_name = None


def get_model(preferred: str = PRIMARY_MODEL):
    """Get the sentence transformer model with three-tier fallback."""
    global _model, _model_name
    if _model is not None:
        return _model, _model_name
    
    for model_name in [preferred, SECONDARY_MODEL, TERTIARY_MODEL]:
        try:
            from sentence_transformers import SentenceTransformer
            print(f"Loading embedding model: {model_name}")
            _model = SentenceTransformer(model_name)
            _model_name = model_name
            print(f"Embedding model loaded: {model_name}")
            return _model, _model_name
        except Exception as e:
            print(f"Model {model_name} failed to load: {e}. Trying next...")
    
    raise RuntimeError(
        "All embedding models failed to load. "
        "Check internet connection or install sentence-transformers."
    )


def embed_reviews(reviews: List[Dict[str, Any]]) -> Tuple[np.ndarray, str]:
    """
    Embed reviews using BAAI/bge-small-en-v1.5 model and store in ChromaDB.
    
    Args:
        reviews: List of review dictionaries
        
    Returns:
        Tuple of (embeddings array, model_name)
    """
    if not reviews:
        model, model_name = get_model()
        return np.array([]), model_name
    
    # Guard: ensure noise filter ran before embedder
    for r in reviews:
        text = r.get("text", "")
        if len(text) > 10100:
            raise ValueError(
                f"Review {r.get('review_id')} has {len(text)} chars. "
                "Noise filter truncation was bypassed. Run apply_noise_filters() first."
            )
    
    # Extract texts from reviews
    texts = [r.get("text", "") for r in reviews]
    
    # Filter out empty texts
    valid_indices = [i for i, text in enumerate(texts) if text.strip()]
    if not valid_indices:
        print("Warning: No valid texts found for embedding")
        model, model_name = get_model()
        return np.array([]), model_name
    
    valid_texts = [texts[i] for i in valid_indices]
    valid_reviews = [reviews[i] for i in valid_indices]
    
    # Get model and encode texts
    model, model_name = get_model()
    print(f"Embedding {len(valid_texts)} reviews...")
    
    embeddings = model.encode(
        valid_texts, 
        batch_size=32, 
        show_progress_bar=True,
        normalize_embeddings=True  # Normalize for cosine similarity
    )
    
    # Store in ChromaDB
    ids = [r["review_id"] for r in valid_reviews]
    metadatas = [
        {
            "store": r.get("store", ""),
            "rating": r.get("rating", 0),
            "date": r.get("date", ""),
            "week_number": r.get("week_number", 0)
        }
        for r in valid_reviews
    ]
    
    try:
        success = upsert_embeddings(ids, embeddings.tolist(), metadatas)
        if success:
            print(f"Successfully stored {len(embeddings)} embeddings in ChromaDB")
        else:
            print("Warning: Failed to store embeddings in ChromaDB")
    except Exception as e:
        print(f"Error storing embeddings: {e}")
    
    return np.array(embeddings), model_name


def embed_single_text(text: str) -> np.ndarray:
    """
    Embed a single text string.
    
    Args:
        text: Text to embed
        
    Returns:
        Embedding array
    """
    if not text or not text.strip():
        return np.array([])
    
    model = get_model()
    embedding = model.encode(text, normalize_embeddings=True)
    return np.array(embedding)


def test_embedder():
    """Test function to verify embedder works correctly."""
    test_reviews = [
        {
            "review_id": "test_1",
            "text": "This app is great and easy to use!",
            "store": "ios",
            "rating": 5,
            "date": "2024-01-01",
            "week_number": 1
        },
        {
            "review_id": "test_2", 
            "text": "The app keeps crashing and is very slow.",
            "store": "android",
            "rating": 1,
            "date": "2024-01-02",
            "week_number": 1
        }
    ]
    
    embeddings, model_name = embed_reviews(test_reviews)
    print(f"Embedded {len(test_reviews)} reviews using {model_name}")
    print(f"Embedding shape: {embeddings.shape}")
    
    # Test single text embedding
    single_embedding = embed_single_text("Test single review")
    print(f"Single text embedding shape: {single_embedding.shape}")


if __name__ == "__main__":
    test_embedder()
