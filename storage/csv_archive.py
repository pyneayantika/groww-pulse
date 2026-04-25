import csv
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any
import pandas as pd

ARCHIVE_DIR = Path("data/archive")

# Define CSV columns with exact 9-column schema
ARCHIVE_COLUMNS = [
    "review_id",       # STRING — unique hash
    "store",           # STRING — ios / android
    "rating",          # INT — 1-5
    "title_clean",     # TEXT — PII-stripped title
    "text_clean",      # TEXT — PII-stripped body
    "date",            # DATE — review date
    "week_number",     # INT — ISO week
    "theme_assigned",  # STRING — T1-T5 label
    "urgency_score",   # FLOAT — 1-10
]


def append_to_archive(reviews: List[Dict[str, Any]], week_number: int, year: int) -> bool:
    """Append reviews to the weekly archive CSV file."""
    try:
        # Ensure archive directory exists
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        
        # Create filename for this week
        filename = f"week_{week_number:02d}_{year}.csv"
        filepath = ARCHIVE_DIR / filename
        
        # Prepare review data for CSV
        rows = []
        for r in reviews:
            rows.append({
                "review_id":      r.get("review_id", ""),
                "store":          r.get("store", ""),
                "rating":         r.get("rating", 0),
                "title_clean":    r.get("title", ""),
                "text_clean":     r.get("text", ""),
                "date":           r.get("date", ""),
                "week_number":    week_number,
                "theme_assigned": r.get("theme_assigned", ""),
                "urgency_score":   r.get("urgency_score", 0.0),
            })
        
        # Check if file exists to determine if we need headers
        file_exists = filepath.exists()
        
        # Append to CSV
        with open(filepath, 'a', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=ARCHIVE_COLUMNS)
            
            # Write header if file is new
            if not file_exists:
                writer.writeheader()
            
            # Write all review data
            writer.writerows(rows)
        
        df = pd.DataFrame(rows, columns=ARCHIVE_COLUMNS)
        
        if filepath.exists():
            existing = pd.read_csv(filepath)
            df = pd.concat([existing, df]).drop_duplicates(
                subset=["review_id"]
            )
        
        df.to_csv(filepath, index=False)
        print(f"Archive updated: {filepath} ({len(df)} rows)")
        
    except Exception as e:
        print(f"Error appending to archive: {e}")
        return False


def rotate_archive() -> int:
    """Delete CSV files older than 84 days based on filename date."""
    try:
        deleted_count = 0
        cutoff_date = datetime.now() - timedelta(days=84)
        
        if not ARCHIVE_DIR.exists():
            return deleted_count
        
        for csv_file in ARCHIVE_DIR.glob("week_*.csv"):
            try:
                # Extract week number and year from filename
                # Format: week_XX_YYYY.csv
                stem = csv_file.stem  # week_XX_YYYY
                parts = stem.split('_')
                
                if len(parts) == 3 and parts[0] == 'week':
                    week_num = int(parts[1])
                    year = int(parts[2])
                    
                    # Calculate the date for this week
                    # Using ISO week date calculation
                    week_start = datetime.strptime(f"{year}-W{week_num:02d}-1", "%Y-W%W-%w")
                    
                    # If this week's file is older than cutoff, delete it
                    if week_start < cutoff_date:
                        csv_file.unlink()
                        deleted_count += 1
                        print(f"Deleted old archive file: {csv_file.name}")
                        
            except (ValueError, IndexError) as e:
                print(f"Could not parse filename {csv_file.name}: {e}")
                continue
        
        print(f"Archive rotation completed. Deleted {deleted_count} files.")
        return deleted_count
        
    except Exception as e:
        print(f"Error during archive rotation: {e}")
        return 0


def export_quarterly(output_path: str, year: int, quarter: int) -> bool:
    """Merge all CSVs for a specific quarter into one file."""
    try:
        # Validate quarter
        if quarter not in [1, 2, 3, 4]:
            raise ValueError("Quarter must be 1, 2, 3, or 4")
        
        # Calculate week ranges for the quarter
        quarter_weeks = {
            1: (1, 13),   # Q1: weeks 1-13
            2: (14, 26),  # Q2: weeks 14-26
            3: (27, 39),  # Q3: weeks 27-39
            4: (40, 52)   # Q4: weeks 40-52
        }
        
        start_week, end_week = quarter_weeks[quarter]
        
        # Find all relevant CSV files
        quarterly_files = []
        for week_num in range(start_week, end_week + 1):
            filename = f"week_{week_num:02d}_{year}.csv"
            filepath = ARCHIVE_DIR / filename
            if filepath.exists():
                quarterly_files.append(filepath)
        
        if not quarterly_files:
            print(f"No archive files found for Q{quarter} {year}")
            return False
        
        # Read and combine all CSV files
        all_data = []
        for csv_file in quarterly_files:
            try:
                df = pd.read_csv(csv_file)
                all_data.append(df)
                print(f"Loaded {len(df)} records from {csv_file.name}")
            except Exception as e:
                print(f"Error reading {csv_file.name}: {e}")
                continue
        
        if not all_data:
            print("No data could be loaded from quarterly files")
            return False
        
        # Combine all dataframes
        combined_df = pd.concat(all_data, ignore_index=True)
        
        # Sort by date if available
        if 'date' in combined_df.columns:
            try:
                combined_df['date'] = pd.to_datetime(combined_df['date'], errors='coerce')
                combined_df = combined_df.sort_values('date', na_position='last')
            except Exception as e:
                print(f"Could not parse dates: {e}")
        
        # Save to output path
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        combined_df.to_csv(output_path, index=False)
        print(f"Quarterly export completed: {len(combined_df)} records saved to {output_path}")
        return True
        
    except Exception as e:
        print(f"Error during quarterly export: {e}")
        return False


def get_archive_stats() -> Dict[str, Any]:
    """Get statistics about the archive."""
    try:
        if not ARCHIVE_DIR.exists():
            return {"total_files": 0, "total_records": 0, "size_mb": 0}
        
        csv_files = list(ARCHIVE_DIR.glob("week_*.csv"))
        total_records = 0
        total_size = 0
        
        for csv_file in csv_files:
            try:
                # Count records without loading full file
                with open(csv_file, 'r', encoding='utf-8') as f:
                    record_count = sum(1 for _ in f) - 1  # Subtract header
                total_records += max(0, record_count)
                total_size += csv_file.stat().st_size
            except Exception:
                continue
        
        return {
            "total_files": len(csv_files),
            "total_records": total_records,
            "size_mb": round(total_size / (1024 * 1024), 2)
        }
        
    except Exception as e:
        print(f"Error getting archive stats: {e}")
        return {"total_files": 0, "total_records": 0, "size_mb": 0}


def list_archive_files() -> List[str]:
    """List all archive files sorted by date."""
    try:
        if not ARCHIVE_DIR.exists():
            return []
        
        csv_files = list(ARCHIVE_DIR.glob("week_*.csv"))
        # Sort by filename (which includes week and year)
        csv_files.sort()
        
        return [f.name for f in csv_files]
        
    except Exception as e:
        print(f"Error listing archive files: {e}")
        return []
