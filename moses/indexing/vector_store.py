import lancedb
from lancedb.pydantic import LanceModel, Vector
from pathlib import Path
import logging

# all-MiniLM-L6-v2 dimension size
EMBEDDING_DIM = 384  

class PromotedRule(LanceModel):
    id: str
    rule_name: str
    pattern_description: str
    destination: str
    vector: Vector(EMBEDDING_DIM)

class CorrectionLog(LanceModel):
    id: str
    filename: str
    original_destination: str
    corrected_destination: str
    signature: str # Truncated text/metadata string representing the file
    vector: Vector(EMBEDDING_DIM)

class FileIndex(LanceModel):
    id: str
    filename: str
    extension: str
    destination: str
    extracted_content: str
    vector: Vector(EMBEDDING_DIM)

def init_db(db_path: Path | str = "./data/lancedb"):
    """Initializes the LanceDB connection and ensures tables exist."""
    path = Path(db_path)
    path.mkdir(parents=True, exist_ok=True)
    
    db = lancedb.connect(str(path))
    
    # Create tables if they don't exist
    if "promoted_rules" not in db.table_names():
        db.create_table("promoted_rules", schema=PromotedRule)
        logging.info("Created 'promoted_rules' table.")
        
    if "correction_log" not in db.table_names():
        db.create_table("correction_log", schema=CorrectionLog)
        logging.info("Created 'correction_log' table.")
        
    if "file_index" not in db.table_names():
        db.create_table("file_index", schema=FileIndex)
        logging.info("Created 'file_index' table.")
        
    return db

def get_table(db, table_name: str):
    return db.open_table(table_name)