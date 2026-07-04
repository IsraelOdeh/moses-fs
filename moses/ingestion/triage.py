import csv
import zipfile
import email
from email import policy
import logging
from pathlib import Path

MAX_CHARS = 2000

def _truncate(text: str) -> str:
    if len(text) > MAX_CHARS:
        return text[:MAX_CHARS] + "\n\n[...TRUNCATED]"
    return text

def parse_code_or_text(filepath: Path) -> str:
    """Extracts first 50 lines and last 20 lines."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            if len(lines) <= 70:
                return _truncate("".join(lines))
            return _truncate("".join(lines[:50]) + "\n\n[...SNIP...]\n\n" + "".join(lines[-20:]))
    except Exception as e:
        return f"Error reading text: {e}"

def parse_csv(filepath: Path) -> str:
    """Extracts headers and 3 sample rows without using pandas."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.reader(f)
            rows = [next(reader) for _ in range(4)]
            return _truncate("\n".join([", ".join(row) for row in rows if row]))
    except StopIteration:
        return "Empty CSV"
    except Exception as e:
        return f"Error reading CSV: {e}"

def parse_archive(filepath: Path) -> str:
    """Safely inspects zip contents without extracting to prevent zip bombs."""
    try:
        with zipfile.ZipFile(filepath, 'r') as zf:
            namelist = zf.namelist()
            sample = namelist[:20]
            count = len(namelist)
            text = f"Archive contains {count} files. Sample:\n" + "\n".join(sample)
            return _truncate(text)
    except zipfile.BadZipFile:
        return "Corrupt or invalid zip archive."

def parse_eml(filepath: Path) -> str:
    """Extracts email headers and plain text body only."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            msg = email.message_from_file(f, policy=policy.default)
            
            headers = f"Subject: {msg['subject']}\nFrom: {msg['from']}\nTo: {msg['to']}\nDate: {msg['date']}\n\n"
            body = ""
            
            if msg.is_multipart():
                for part in msg.iter_parts():
                    if part.get_content_type() == 'text/plain':
                        body = part.get_content()
                        break
            else:
                body = msg.get_content()
                
            return _truncate(headers + body)
    except Exception as e:
        return f"Error parsing EML: {e}"

def triage_file(filepath: Path) -> dict:
    """Master router returning a schema-ready JSON dictionary for the LLM."""
    ext = filepath.suffix.lower()
    payload = {
        "filename": filepath.name,
        "extension": ext,
        "size_bytes": filepath.stat().st_size,
        "extracted_content": None
    }
    logging.info(f"Triage initiated for {filepath.name} with extension {ext}.payload = {payload}")
    
    if ext in ['.py', '.cpp', '.m', '.js', '.md', '.tex', '.txt']:
        payload["extracted_content"] = parse_code_or_text(filepath)
    elif ext in ['.csv']:
        payload["extracted_content"] = parse_csv(filepath)
    elif ext in ['.zip']:
        payload["extracted_content"] = parse_archive(filepath)
    elif ext in ['.eml']:
        payload["extracted_content"] = parse_eml(filepath)
    else:
        logging.info(f"No specific extractor for {ext}. Proceeding with metadata only.")
        
    return payload