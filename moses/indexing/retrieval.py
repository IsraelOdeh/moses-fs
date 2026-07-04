import logging
from typing import List, Dict, Optional

# Threshold for L2 distance (lower is closer).
# You will need to tune this based on benchmark testing.
MAX_DISTANCE_FLOOR = 0.65  

def _search_table(table, query_vector: List[float], limit: int = 3) -> List[Dict]:
    """Helper to perform vector search and return raw dicts."""
    try:
        results = table.search(query_vector).limit(limit).to_list()
        # Filter out results that are too far away conceptually
        valid_results = [r for r in results if r["_distance"] <= MAX_DISTANCE_FLOOR]
        return valid_results
    except Exception as e:
        logging.error(f"Vector search failed: {e}")
        return []

def gather_context(db, query_vector: List[float], file_metadata: dict) -> dict:
    """
    Searches all three tiers of precedent.
    Returns a context dictionary to be injected into the LLM prompt.
    """
    context = {
        "matched_rule": None,
        "corrections": [],
        "precedents": []
    }
    
    # 1. Check Promoted Rules (Highest Priority)
    rules_table = db.open_table("promoted_rules")
    rules = _search_table(rules_table, query_vector, limit=1)
    if rules and rules[0]["_distance"] < 0.3: # Very strict threshold for hard rules
        context["matched_rule"] = rules[0]
        logging.info(f"Matched hard rule: {rules[0]['rule_name']}")
        return context # Shortcut return; no need for LLM

    # 2. Check Correction Log (Past Mistakes)
    corrections_table = db.open_table("correction_log")
    corrections = _search_table(corrections_table, query_vector, limit=2)
    if corrections:
        context["corrections"] = corrections
        logging.info(f"Found {len(corrections)} relevant past corrections.")

    # 3. Check File Index (Past Successes)
    index_table = db.open_table("file_index")
    # We pass a post-filter to only look at files with the same extension
    try:
        ext = file_metadata.get("extension", "")
        precedents = (
            index_table.search(query_vector)
            .where(f"extension = '{ext}'")
            .limit(3)
            .to_list()
        )
        valid_precedents = [p for p in precedents if p["_distance"] <= MAX_DISTANCE_FLOOR]
        context["precedents"] = valid_precedents
    except Exception as e:
        logging.warning(f"File index retrieval failed or returned empty: {e}")

    return context