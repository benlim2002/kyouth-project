import sqlite3
import pandas as pd
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

def init_db(conn):
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS properties (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            township TEXT,
            area TEXT,
            state TEXT,
            tenure TEXT,
            type TEXT,
            median_price REAL,
            median_psf REAL,
            transactions INTEGER,
            amenities TEXT,
            growth_potential TEXT,
            tags TEXT,
            summary TEXT
        )
    """)
    conn.commit()
    logging.info("LOAD | ✅ Table created (or already exists)")


def load_csv_to_db(csv_path, db_path):
    csv_path = Path(csv_path)
    db_path = Path(db_path)

    if not csv_path.exists():
        logging.error(f"LOAD | ❌ CSV not found at {csv_path}")
        return

    df = pd.read_csv(csv_path)
    logging.info(f"LOAD | 📂 Loaded {len(df)} rows from {csv_path.name}")

    # normalise column names
    df.columns = [c.strip().lower() for c in df.columns]

    # add empty enrichment columns
    for col in ["amenities", "growth_potential", "tags", "summary"]:
        df[col] = None

    conn = sqlite3.connect(db_path)
    init_db(conn)
    cursor = conn.cursor()

    inserted = 0
    skipped = 0

    for _, row in df.iterrows():
        try:
            cursor.execute("""
                INSERT INTO properties (
                    township, area, state, tenure, type,
                    median_price, median_psf, transactions,
                    amenities, growth_potential, tags, summary
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                row.get("township"),
                row.get("area"),
                row.get("state"),
                row.get("tenure"),
                row.get("type"),
                row.get("median_price"),
                row.get("median_psf"),
                row.get("transactions"),
                None, None, None, None  # enrichment columns, empty for now
            ))
            inserted += 1
        except Exception as e:
            logging.warning(f"LOAD | ⚠️ Skipped row — {e}")
            skipped += 1

    conn.commit()
    conn.close()

    logging.info(f"LOAD | ✅ Inserted: {inserted} | Skipped: {skipped}")
    logging.info(f"LOAD | 💾 Database saved to {db_path}")


if __name__ == "__main__":
    # paths are relative to this file (backend/dataProcess/)
    BASE_DIR = Path(__file__).resolve().parents[2] 

    load_csv_to_db(
        csv_path=BASE_DIR / "data" / "malaysia_house_price_data_2025.csv", 
        db_path=BASE_DIR / "data" / "data.db"
    )