import gc
import logging
from pathlib import Path
import threading
from llama_cpp import Llama
import ctypes
import multiprocessing

# Global state to track what is currently occupying our RAM
_active_model_instance = None
_active_model_name = None
_unload_timer = None
_active_model_users = 0
_model_lock = threading.RLock()

optimal_threads = max(1, multiprocessing.cpu_count() // 2)

IDLE_TIMEOUT_SECONDS = 10.0

def _reset_idle_timer():
    """Starts or resets the countdown clock for the active model."""
    global _unload_timer
    
    # Cancel the existing countdown if a new file just came in
    if _unload_timer is not None:
        _unload_timer.cancel()
        
    # Start a fresh countdown in a background daemon thread
    _unload_timer = threading.Timer(IDLE_TIMEOUT_SECONDS, _force_unload)
    _unload_timer.daemon = True
    _unload_timer.start()

def acquire_model():
    """Marks the current model as in use so it will not be unloaded mid-call."""
    global _active_model_users

    with _model_lock:
        _active_model_users += 1

def release_model():
    """Releases a model usage marker after inference completes."""
    global _active_model_users

    with _model_lock:
        if _active_model_users > 0:
            _active_model_users -= 1

def _switch_model(target_name: str, load_logic: callable) -> Llama:
    """Internal helper to manage swapping and timer resets."""
    global _active_model_name, _active_model_instance
    
    with _model_lock:
        if _active_model_name != target_name:
            # We need a different model, so kill the current one immediately
            if _active_model_instance is not None:
                _force_unload()
            
            logging.info(f"Loading {target_name} into RAM...")
            _active_model_instance = load_logic()
            _active_model_name = target_name

        # Reset the clock every time the model is requested
        _reset_idle_timer()
        return _active_model_instance

def _force_unload():
    """Destroys the current model, clears C-pointers, and forces OS reclamation."""
    global _active_model_instance, _active_model_name, _active_model_users

    with _model_lock:
        if _active_model_instance is None:
            return

        if _active_model_users > 0:
            logging.info(f"Deferring unload of {_active_model_name}; model is still in use.")
            _reset_idle_timer()
            return

        logging.info(f"Purging {_active_model_name} from RAM...")

        # 1. Force llama_cpp_python to explicitly free the C-level memory pointers
        if hasattr(_active_model_instance, 'close'):
            _active_model_instance.close()

        # 2. Delete the Python reference
        del _active_model_instance
        _active_model_instance = None
        _active_model_name = None

        # 3. Run Python's garbage collector
        gc.collect()

        # 4. Force the Linux OS to immediately reclaim the freed memory
        # This targets the glibc allocator used in Ubuntu/WSL2
        try:
            libc = ctypes.CDLL("libc.so.6")
            libc.malloc_trim(0)
            logging.info("OS memory reclamation successful (malloc_trim).")
        except Exception:
            # This will silently pass if you run it natively on Windows without WSL2,
            # but will execute perfectly when the ADTC profiler runs it on Ubuntu.
            pass
        
def get_embedder() -> Llama:
    """Returns the embedding model, unloading others if necessary."""
    def load_embedder():
        logging.info("Loading all-MiniLM-L6-v2 into RAM...")
        model_path = Path("model/all-MiniLM-L6-v2-Q8_0.gguf")
        return Llama(model_path=str(model_path), embedding=True, verbose=False, n_threads=optimal_threads, )
    
    return _switch_model("minilm", load_embedder)
    
def get_classifier() -> Llama:
    """Returns the Qwen2.5 model, unloading others if necessary."""
    def load_classifier():
        logging.info("Loading Qwen2.5-1.5B into RAM...")
        

        model_path = Path("model/qwen2.5-1.5b-instruct-q4_k_m.gguf")
        return Llama(model_path=str(model_path), n_ctx=1024, n_batch=600, n_threads=optimal_threads, flash_attn=True, verbose=False)
    
    return _switch_model("qwen", load_classifier)

def get_vision_model() -> Llama:
    """Returns Moondream2, unloading others if necessary."""
    def load_vision():
        logging.info("Loading Moondream2 into RAM...")
        model_path = Path("model/moondream2-q4.gguf")
        return Llama(model_path=str(model_path), chat_handler=None, verbose=False, n_threads=optimal_threads)
    
    return _switch_model("moondream", load_vision)