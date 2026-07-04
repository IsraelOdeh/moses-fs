import argparse
import time
import logging
import os
import sys
from pathlib import Path

# Allow direct execution (python moses/cli.py) by adding project root to sys.path.
if __package__ is None or __package__ == "":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from moses.memory_guard import start_guard
from moses.ingestion.watchdog_service import start_watchdog

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

def run_headless(target_dir: str):
    logging.info("Starting MOSES.fs in headless mode...")
    
    # 1. Boot Resource Monitor
    stop_guard_event = start_guard()
    
    # 2. Boot Detection Service
    observer, worker_stop_event = start_watchdog(target_dir)
    
    try:
        # Keep the main thread alive while background threads do the work
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("Keyboard interrupt received. Shutting down MOSES.fs...")
        observer.stop()
        worker_stop_event.set()
        stop_guard_event.set()
        
    observer.join()
    logging.info("MOSES.fs Shutdown complete.")

def main():
    parser = argparse.ArgumentParser(description="MOSES.fs - Semantic File Organizer")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    run_parser = subparsers.add_parser("run", help="Start the main pipeline")
    run_parser.add_argument("--headless", action="store_true", help="Run without the Textual GUI")
    run_parser.add_argument("--dir", type=str, default="./data/staging", help="Directory to watch")
    
    args = parser.parse_args()
    
    if args.command == "run":
        if args.headless:
            run_headless(args.dir)
        else:
            print("GUI mode not yet implemented. Please use --headless.")

if __name__ == "__main__":
    main()