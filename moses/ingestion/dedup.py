import hashlib
import os
import shutil
import logging
from pathlib import Path

# In a real run, this dict would be populated by querying LanceDB first.
# We'll use an in-memory set here for the local run logic.
_known_hashes = {
    "b5331f981ba9c0662ca077ffa244fbd95ad3ee879f0f9219e673856af1f27a05": Path("/data/staging/COMP_README copy.md"),
    "d7a8fbb307d7bef6e6e15c3b6c6d8c8d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1": Path("/original/file2.bin"),
} 

def calculate_sha256(filepath: Path, chunk_size: int = 8192) -> str:
    """Calculates SHA-256 without loading the entire file into RAM."""
    hasher = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            hasher.update(chunk)
    return hasher.hexdigest()

def handle_duplicate(filepath: Path, original_path: Path, trash_dir: Path):
    """Moves duplicate to trash and creates a symlink."""
    trash_dir.mkdir(parents=True, exist_ok=True)
    trashed_file = trash_dir / f"{filepath.name}_{hash(filepath.name)}"
    
    shutil.move(str(filepath), str(trashed_file))
    logging.info(f"Duplicate found. Moved {filepath.name} to {trash_dir}")
    
    try:
        os.symlink(original_path, filepath)
        logging.info(f"Symlink created at {filepath} pointing to {original_path}")
    except OSError:
        logging.warning("OS prevented symlink creation (Enable Windows Developer Mode). File simply trashed.")

def process_dedup(filepath: Path, trash_dir: Path) -> bool:
    """Returns True if the file was a duplicate and handled."""
    
    logging.info(f"Processing deduplication for {filepath.name}")
    file_hash = calculate_sha256(filepath)
    logging.info(f"Calculated SHA-256 for {filepath.name}: {file_hash}")
    if file_hash in _known_hashes:
        handle_duplicate(filepath, _known_hashes[file_hash], trash_dir)
        logging.info(f"Duplicate detected for {filepath.name}. Original at {_known_hashes[file_hash]}")
        return True
        
    _known_hashes[file_hash] = filepath
    return False