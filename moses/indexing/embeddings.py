import logging
from pathlib import Path
from llama_cpp import Llama
from moses.cognition.multiplexer import acquire_model, get_embedder, release_model


def generate_embedding(text: str, model_path: Path = Path("model/all-MiniLM-L6-v2-Q8_0.gguf")) -> list[float]:
    """Generates a 384-dimensional vector using all-MiniLM via llama.cpp."""
    global _embedder
    
    logging.info("Requesting embedder from Multiplexer...")
    embedder = get_embedder()
    
    logging.info("Calculating file signature embedding...")
    acquire_model()
    try:
        response = embedder.create_embedding(text)
        return response["data"][0]["embedding"]
    finally:
        release_model()