import json
import logging
from llama_cpp import LlamaGrammar
from moses.cognition.multiplexer import acquire_model, get_classifier, release_model

# Define the strict output structure we expect from Qwen
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "destination": {
            "type": "string",
            "description": "The absolute or relative directory path where this file should be moved (e.g., './Documents/Invoices/2026/')."
        },
        "reasoning": {
            "type": "string",
            "description": "A very brief, 1-sentence explanation of why this destination was chosen."
        },
        "confidence": {
            "type": "number",
            "description": "A confidence score between 0.0 and 1.0."
        }
    },
    "required": ["destination", "reasoning", "confidence"]
}

def _build_prompt(metadata: dict, context: dict) -> str:
    """Constructs a prompt injecting file data and LanceDB history."""
    
    system_msg = (
        "You are an automated file organizer system named MOSES.fs. "
        "Look at a file's metadata and content, and determine the best folder to put it in. "
        "You must follow historical precedents if they are provided."
    )
    
    # 1. Inject the new file's data
    user_msg = (
        f"FILE:\n"
        f"- Name: {metadata.get('filename')}\n"
        f"- Extension: {metadata.get('extension')}\n"
        f"- Size: {metadata.get('size_bytes')} bytes\n"
        f"- Extracted Content:\n{metadata.get('extracted_content', 'None')}\n\n"
    )
    
    # 2. Inject Past Corrections (Highest LLM Priority)
    corrections = context.get('corrections', [])
    if corrections:
        user_msg += "PAST CORRECTIONS (Avoid these mistakes!):\n"
        for c in corrections:
            user_msg += f"- You previously moved '{c['filename']}' to '{c['original_destination']}', user corrected it to '{c['corrected_destination']}'.\n"
        user_msg += "\n"
        
    # 3. Inject Successful Precedents (Few-Shot Examples)
    precedents = context.get('precedents', [])
    if precedents:
        user_msg += "HISTORICAL PRECEDENTS (Do what worked before!):\n"
        for p in precedents:
            user_msg += f"- Successfully moved '{p['filename']}' to '{p['destination']}'.\n"
    else:
        user_msg += "HISTORICAL PRECEDENTS: None. Use your best logical judgment based on the file content.\n"

    # Format strictly for Qwen2.5 ChatML template
    prompt = (
        f"<|im_start|>system\n{system_msg}<|im_end|>\n"
        f"<|im_start|>user\n{user_msg}<|im_end|>\n"
        f"<|im_start|>assistant\n"
    )
    
    return prompt

def classify_file(metadata: dict, context: dict) -> dict:
    """Loads Qwen, prompts it, and returns a validated JSON dictionary."""
    logging.info("Requesting Qwen2.5 from Multiplexer...")
    acquire_model()
    llm = get_classifier()
    
    prompt = _build_prompt(metadata, context)
    
    grammer_json = json.dumps(OUTPUT_SCHEMA)
    grammer = LlamaGrammar.from_json_schema(grammer_json)
    
    logging.info("Generating routing decision...")
    
    try:
        response = llm(
            prompt,
            max_tokens=250,           # We only need a short JSON string
            temperature=0.1,           # Keep it highly deterministic
            grammar=grammer
        )
        
        raw_text = response["choices"][0]["text"]
    finally:
        release_model()
    
    logging.info(type(raw_text))
    try:
        decision = json.loads(raw_text)
        logging.info(f"LLM Decision: {decision['destination']} (Confidence: {decision['confidence']})")
        return decision
    except json.JSONDecodeError:
        logging.error(f"LLM failed to return valid JSON. Raw output: {raw_text}")
        # Fallback safeguard
        return {
            "destination": "./Unsorted/",
            "reasoning": "Fallback due to JSON parse error.",
            "confidence": 0.0
        }