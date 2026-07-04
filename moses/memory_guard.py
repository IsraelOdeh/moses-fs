import os
import time
import psutil
import threading
import logging

# 6.5 GB limit per ADTC rules
MAX_RSS_BYTES = 6.5 * 1024 * 1024 * 1024  
CHECK_INTERVAL = 2.0  # seconds

def monitor_memory(stop_event: threading.Event):
    process = psutil.Process(os.getpid())
    logging.info("Memory Guard initialized. Limit set to 6.5GB.")
    
    while not stop_event.is_set():
        # Get RSS of current process
        rss = process.memory_info().rss
        
        # Account for any spawned child processes (e.g., llama.cpp wrappers)
        for child in process.children(recursive=True):
            try:
                rss += child.memory_info().rss
            except psutil.NoSuchProcess:
                pass
                
        if rss > MAX_RSS_BYTES:
            logging.error(f"CRITICAL: Memory threshold exceeded! Current RSS: {rss / (1024**3):.2f} GB")
            # TODO: Trigger Multiplexer.force_unload() to drop LLM from RAM
            
        logging.info("Current RSS: {:.2f} GB".format(rss / (1024**3)))
        time.sleep(CHECK_INTERVAL)

def start_guard() -> threading.Event:
    stop_event = threading.Event()
    thread = threading.Thread(target=monitor_memory, args=(stop_event,), daemon=True)
    thread.start()
    return stop_event