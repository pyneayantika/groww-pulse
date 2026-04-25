import hashlib
import pandas as pd
from pathlib import Path
from typing import Dict, Any, List
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_csv_reviews(filepath: str) -> List[Dict[str, Any]]:
    """Load reviews from CSV file with auto-detection of columns."""
    try:
        # Read CSV file
        df = pd.read_csv(filepath)
        
        # Auto-detect column mappings
        text_columns = ['text', 'review_text', 'body', 'content', 'review', 'comment']
        rating_columns = ['score', 'stars', 'rating', 'rate']
        date_columns = ['at', 'review_date', 'date', 'created_at', 'timestamp']
        
        # Find actual column names
        text_col = None
        rating_col = None
        date_col = None
        
        for col in df.columns:
            col_lower = col.lower()
            if text_col is None and col_lower in text_columns:
                text_col = col
            if rating_col is None and col_lower in rating_columns:
                rating_col = col
            if date_col is None and col_lower in date_columns:
                date_col = col
        
        if text_col is None:
            logger.error("Could not find text/review column in CSV")
            return []
        
        logger.info(f"Detected columns: text={text_col}, rating={rating_col}, date={date_col}")
        
        reviews = []
        for idx, row in df.iterrows():
            try:
                # Get text content
                text = str(row[text_col]) if pd.notna(row[text_col]) else ''
                
                # Skip if text is too short or empty
                if len(text.strip()) < 20:
                    continue
                
                # Get rating (default to 3 if not found)
                rating = 3
                if rating_col and rating_col in row and pd.notna(row[rating_col]):
                    try:
                        rating = int(row[rating_col])
                    except (ValueError, TypeError):
                        rating = 3
                
                # Get date (use today's date if not found)
                date_str = pd.Timestamp.now().strftime('%Y-%m-%d')
                if date_col and date_col in row and pd.notna(row[date_col]):
                    try:
                        date_obj = pd.to_datetime(row[date_col])
                        date_str = date_obj.strftime('%Y-%m-%d')
                    except:
                        date_str = pd.Timestamp.now().strftime('%Y-%m-%d')
                
                # Generate review_id
                review_id_input = f"csv{idx}{date_str}"
                review_id = hashlib.sha256(review_id_input.encode('utf-8')).hexdigest()
                
                # Create review dict
                review = {
                    'review_id': review_id,
                    'store': 'csv',
                    'rating': rating,
                    'title': '',  # CSV files typically don't have titles
                    'text': text,
                    'date': date_str,
                    'app_version': '',
                    'raw_id': str(idx)
                }
                
                reviews.append(review)
                
            except Exception as e:
                logger.warning(f"Error processing row {idx}: {e}")
                continue
        
        logger.info(f"Successfully loaded {len(reviews)} reviews from CSV")
        return reviews
        
    except FileNotFoundError:
        logger.error(f"CSV file not found: {filepath}")
        return []
    except Exception as e:
        logger.error(f"Error loading CSV file {filepath}: {e}")
        return []


def test_csv_fallback():
    """Test function to verify CSV fallback works."""
    # Create a test CSV file
    test_data = {
        'review_text': [
            'This app is really great and I love using it every day!',
            'The app keeps crashing and is very slow to load.',
            'Good interface but needs more features.',
            'Too short',  # This should be filtered out
            'Excellent trading platform with good customer support.'
        ],
        'rating': [5, 1, 3, 2, 5],
        'date': ['2024-01-01', '2024-01-02', '2024-01-03', '2024-01-04', '2024-01-05']
    }
    
    test_df = pd.DataFrame(test_data)
    test_csv_path = Path('test_reviews.csv')
    test_df.to_csv(test_csv_path, index=False)
    
    # Test loading
    reviews = load_csv_reviews(str(test_csv_path))
    print(f"Loaded {len(reviews)} reviews from test CSV")
    
    # Clean up
    test_csv_path.unlink()
    
    # Print sample
    if reviews:
        print("Sample review:")
        sample = reviews[0]
        for key, value in sample.items():
            print(f"  {key}: {value}")


if __name__ == "__main__":
    test_csv_fallback()
