import queue
import time
import logging
import threading
from pathlib import Path

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from moses.cognition.classifier import classify_file
from moses.ingestion.triage import triage_file
from moses.ingestion.dedup import process_dedup

# --- Pipeline Imports ---
from moses.ingestion.dedup import process_dedup
from moses.ingestion.triage import triage_file
from moses.indexing.embeddings import generate_embedding
from moses.indexing.vector_store import init_db
from moses.indexing.retrieval import gather_context

# Thread-safe queue for incoming files
file_queue = queue.Queue()
# Initialize LanceDB once on boot
db = init_db()

SETTLING_TIME_SECONDS = 3.0

def process_new_file(filepath: Path):
    """The master integration pipeline stringing Phase 1 -> 3 together."""
    logging.info(f"--- Pipeline started for: {filepath.name} ---")
    
    # Phase 2: Deduplication
    trash_dir = filepath.parent / ".trash"
    if process_dedup(filepath, trash_dir):
        return  # Pipeline aborts early; duplicate handled
        
    # Phase 2: Triage & Extraction
    metadata = triage_file(filepath)
    
    # Phase 3: Vectorization
    # We combine metadata and text to create a rich semantic signature
    signature = (
        f"Filename: {metadata['filename']}\n"
        f"Type: {metadata['extension']}\n"
        f"Content: {metadata['extracted_content']}"
    )
    vector = generate_embedding(signature)
    
    # Phase 3: Context Retrieval
    context = gather_context(db, vector, metadata)
    
    if context.get("matched_rule"):
        logging.info(f"Hard rule matched: {context['matched_rule']['rule_name']}. Bypassing LLM.")
        # TODO: Route directly to Actuator (Phase 5)
        return
        
    logging.info(
        f"Context gathered: {len(context.get('corrections', []))} past corrections, "
        f"{len(context.get('precedents', []))} successful precedents."
    )
    
    # TODO: Pass metadata, vector, and context to Multiplexer -> LLM (Phase 4)

def batch_processing_worker(stop_event: threading.Event):
    """Background worker that accumulates files and processes them in optimal model stages."""
    logging.info("Batch processing worker started.")
    
    batch_buffer = []
    
    while not stop_event.is_set():
        
        # 1. Accumulate files currently sitting in the queue
        while not file_queue.empty():
            batch_buffer.append(file_queue.get())
            
        if not batch_buffer:
            time.sleep(1)  # Quiet period, wait for new files
            continue
        
        # check if the last file in the batch was created more than `SETTLING_TIME_SECONDS` ago
        real_files = [f for f in batch_buffer if not f.is_symlink()]
        if not real_files:
            continue

        last_file_time = max(f.stat().st_ctime for f in real_files)
        
        if time.time() - last_file_time < SETTLING_TIME_SECONDS:
            time.sleep(1)  # Wait for more files to arrive
            continue
            
        batch = batch_buffer

        logging.info(f"⚡ Processing a batch of {len(batch_buffer)} files...")
        
        batch_buffer = []
        
        
        # STAGE 1: Deterministic Triage & Vectorization (Locks in all-MiniLM)
        prepared_files = []
        # trash_dir = batch[0].parent / ".trash" if batch else 
        trash_dir = Path("./data/.trash")
        
        for filepath in batch:
            if not filepath.exists():
                continue
            if process_dedup(filepath, trash_dir):
                continue  # Skip duplicates
                
            metadata = triage_file(filepath)
            
            # Generate embedding signature while all-MiniLM stays warm in RAM
            signature = f"Filename: {metadata['filename']}\nType: {metadata['extension']}\nContent: {metadata['extracted_content']}"
            vector = generate_embedding(signature)
            
            # Gather past context
            context = gather_context(db, vector, metadata)
            
            prepared_files.append({
                "filepath": filepath,
                "metadata": metadata,
                "vector": vector,
                "context": context
            })
            
        # STAGE 2: Cognition & Actuation (Swaps to Qwen/Moondream once)                
        for item in prepared_files:
            logging.info(f"Sending {item['filepath'].name} to LLM Classifier with historical context.")
            if item["context"].get("matched_rule"):
                logging.info(f"Fast-tracking {item['filepath'].name} via hard rule.")
                decision = {"destination": item["context"]["matched_rule"]["destination"], "reasoning": "Matched Hard Rule", "confidence": 1.0}
            else:
                logging.info(f"Sending {item['filepath'].name} to LLM Classifier...")
                decision = classify_file(item["metadata"], item["context"])
            
                logging.info(f"LLM Decision for {item['filepath'].name}: {decision}")

class IngestionHandler(FileSystemEventHandler):
    def on_created(self, event):
        # Ignore directory creation events, focus only on files
        if event.is_directory:
            return
        
        filepath = Path(event.src_path)
        # Ignore symlinks (created by our own dedup handler)
        if filepath.is_symlink():
            logging.debug(f"Ignoring symlink: {filepath.name}")
            return
        
        # Add to queue
        logging.info(f"Queued file for batch processing: {Path(event.src_path).name}")
        file_queue.put(Path(event.src_path))


def start_watchdog(target_directory: str | Path) -> Observer:
    target_path = Path(target_directory)
    if not target_path.exists():
        target_path.mkdir(parents=True, exist_ok=True)
        
    event_handler = IngestionHandler()
    observer = Observer()
    
    # Schedule the observer to watch the target path recursively
    observer.schedule(event_handler, str(target_path), recursive=True)
    observer.start()
    
    # Start the background batch processing thread
    stop_event = threading.Event()
    worker_thread = threading.Thread(target=batch_processing_worker, args=(stop_event,), daemon=True)
    worker_thread.start()
    
    logging.info(f"Watchdog actively monitoring: {target_path.resolve()}")
    return observer, stop_event