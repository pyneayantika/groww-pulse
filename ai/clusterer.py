import numpy as np
from sklearn.cluster import KMeans
import yaml
from pathlib import Path
from typing import List, Dict, Any, Tuple
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def load_taxonomy():
    """Load theme taxonomy from config.yaml."""
    config_path = Path(__file__).parent.parent / "config.yaml"
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        return config["themes"]
    except Exception as e:
        print(f"Error loading taxonomy: {e}")
        # Return default taxonomy if config fails
        return [
            {"id": "T1", "label": "General Feedback", "keywords": ["app", "feature", "issue"]},
            {"id": "T2", "label": "Performance", "keywords": ["slow", "crash", "bug"]},
            {"id": "T3", "label": "UI/UX", "keywords": ["interface", "design", "navigation"]},
            {"id": "T4", "label": "Features", "keywords": ["new", "missing", "request"]},
            {"id": "T5", "label": "Support", "keywords": ["help", "contact", "response"]},
        ]


def map_to_taxonomy(keywords: List[str], taxonomy: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Map extracted keywords to the best matching theme from taxonomy."""
    if not keywords:
        return taxonomy[0]
    
    best_theme = taxonomy[0]
    best_score = 0
    
    # Convert keywords to lowercase for matching
    keywords_lower = [k.lower() for k in keywords]
    
    for theme in taxonomy:
        theme_keywords = [kw.lower() for kw in theme.get("keywords", [])]
        overlap = len(set(keywords_lower) & set(theme_keywords))
        
        # Also check for partial matches
        for kw in keywords_lower:
            for theme_kw in theme_keywords:
                if kw in theme_kw or theme_kw in kw:
                    overlap += 0.5
        
        if overlap > best_score:
            best_score = overlap
            best_theme = theme
    
    return best_theme


def cluster_reviews(texts: List[str], embeddings: np.ndarray, n_reviews: int) -> Dict[str, Any]:
    """
    Cluster reviews using BERTopic or KMeans fallback.
    
    Args:
        texts: List of review texts
        embeddings: numpy array of embeddings
        n_reviews: Number of reviews for determining algorithm choice
        
    Returns:
        Dictionary with clusters and algorithm used
    """
    if n_reviews == 0:
        return {"clusters": [], "algorithm_used": "no_reviews"}
    
    taxonomy = load_taxonomy()
    
    # Try BERTopic for larger datasets
    if n_reviews >= 50:
        try:
            from bertopic import BERTopic
            from sklearn.feature_extraction.text import CountVectorizer
            
            print("Using BERTopic for clustering...")
            
            # Configure vectorizer
            vectorizer = CountVectorizer(
                stop_words="english", 
                min_df=2,
                max_df=0.8,
                ngram_range=(1, 2)
            )
            
            # Configure BERTopic
            model = BERTopic(
                embedding_model=None,  # Use pre-computed embeddings
                vectorizer_model=vectorizer,
                nr_topics=min(5, max(3, n_reviews // 10)),
                min_topic_size=max(5, n_reviews // 20),
                calculate_probabilities=True,
                verbose=False,
                diversity_threshold=0.1
            )
            
            # Fit the model
            topics, probs = model.fit_transform(texts, embeddings)
            
            # Extract clusters
            clusters = []
            topic_info = model.get_topic_info()
            
            for _, row in topic_info.iterrows():
                if row["Topic"] == -1:  # Skip outlier topic
                    continue
                
                topic_id = row["Topic"]
                
                # Get keywords for this topic
                topic_keywords = model.get_topic(topic_id)
                keywords = [w for w, _ in topic_keywords[:10]]
                
                # Get review indices for this topic
                indices = [i for i, t in enumerate(topics) if t == topic_id]
                
                if not indices or len(indices) < 3:  # Skip very small clusters
                    continue
                
                # Map to taxonomy
                theme = map_to_taxonomy(keywords, taxonomy)
                
                clusters.append({
                    "theme_id": theme["id"],
                    "label": theme["label"],
                    "review_indices": indices,
                    "keywords": keywords,
                    "size": len(indices)
                })
                
                if len(clusters) >= 5:  # Limit to top 5 clusters
                    break
            
            if len(clusters) >= 3:
                print(f"BERTopic found {len(clusters)} clusters")
                return {"clusters": clusters, "algorithm_used": "bertopic"}
            else:
                print(f"BERTopic found only {len(clusters)} clusters, falling back to KMeans")
                
        except ImportError:
            print("BERTopic not available, falling back to KMeans")
        except Exception as e:
            print(f"BERTopic failed: {e}, falling back to KMeans")
    
    # KMeans fallback
    print("Using KMeans for clustering...")
    
    # Determine optimal number of clusters
    k = min(5, max(3, n_reviews // 5))
    
    km = KMeans(n_clusters=k, random_state=42, n_init=10, max_iter=300)
    km.fit(embeddings)
    
    clusters = []
    for cluster_id in range(k):
        indices = [i for i, label in enumerate(km.labels_) if label == cluster_id]
        
        if len(indices) < 2:  # Skip very small clusters
            continue
        
        # Extract keywords from cluster texts
        cluster_texts = [texts[i] for i in indices[:20]]  # Limit to first 20 for efficiency
        combined_text = " ".join(cluster_texts).lower()
        
        # Simple keyword extraction (word frequency)
        words = combined_text.split()
        word_freq = {}
        for word in words:
            if len(word) > 3:  # Skip very short words
                word_freq[word] = word_freq.get(word, 0) + 1
        
        # Get top keywords
        keywords = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:10]
        keywords = [kw for kw, _ in keywords]
        
        # Map to taxonomy
        theme = map_to_taxonomy(keywords, taxonomy)
        
        clusters.append({
            "theme_id": theme["id"],
            "label": theme["label"],
            "review_indices": indices,
            "keywords": keywords,
            "size": len(indices)
        })
    
    # Sort clusters by size
    clusters.sort(key=lambda x: x["size"], reverse=True)
    clusters = clusters[:5]  # Limit to top 5
    
    print(f"KMeans found {len(clusters)} clusters")
    return {"clusters": clusters, "algorithm_used": "kmeans"}


def test_clusterer():
    """Test function to verify clusterer works correctly."""
    # Create test data
    test_texts = [
        "The app is great and easy to use for trading",
        "I love the interface and features of this investment app",
        "Best trading platform with good customer support",
        "The app keeps crashing when I try to buy stocks",
        "Very slow performance and frequent bugs",
        "The app freezes and I lose my trades",
        "Need more features like mutual funds and SIP",
        "Please add more investment options and research tools",
        "The KYC process is complicated and takes too long",
        "Customer support is not responding to my queries"
    ]
    
    # Create dummy embeddings
    test_embeddings = np.random.rand(len(test_texts), 384)  # BGE-small dimension
    
    # Test clustering
    result = cluster_reviews(test_texts, test_embeddings, len(test_texts))
    
    print(f"Clustering result: {result['algorithm_used']}")
    print(f"Found {len(result['clusters'])} clusters:")
    
    for i, cluster in enumerate(result['clusters']):
        print(f"  Cluster {i+1}: {cluster['label']} (size: {cluster['size']})")
        print(f"    Keywords: {cluster['keywords'][:5]}")


if __name__ == "__main__":
    test_clusterer()
