#!/usr/bin/env bash
# Download all model weight files required by MOSES.fs.
#
# Rules:
#   - Must be idempotent (safe to run multiple times).
#   - Must download without any credentials (public URL only).
#   - The primary model's output path must match `_runtime.model_path` in metadata.json.
#
# MOSES.fs uses three models total, loaded sequentially by the memory multiplexer
# (never concurrently) to stay under the 7GB RAM ceiling:
#   1. Qwen2.5-1.5B-Instruct  — primary reasoning/classification model (declared in metadata.json)
#   2. Moondream2              — vision model, requires TWO files (text model + mmproj)
#   3. all-MiniLM-L6-v2        — embedding model for semantic indexing

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODEL_DIR="$HERE/model"

mkdir -p "$MODEL_DIR"

echo "==========================================="
echo " MOSES.fs - Downloading GGUF Model Weights "
echo "==========================================="

# ── Pinned model files ───────────────────────────────────────────────────────
# name | url | output filename | approx size (for progress message only)

declare -a MODELS=(
  "Qwen2.5-1.5B-Instruct (primary)|https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf|qwen2.5-1.5b-instruct-q4_k_m.gguf|~1.1 GB"
  "Moondream2 text model|https://huggingface.co/ggml-org/moondream2-20250414-GGUF/resolve/main/moondream2-text-model-f16_ct-vicuna.gguf|moondream2-text-model-f16.gguf|~2.8 GB"
  "Moondream2 mmproj|https://huggingface.co/ggml-org/moondream2-20250414-GGUF/resolve/main/moondream2-mmproj-f16-20250414.gguf|moondream2-mmproj-f16.gguf|~470 MB"
  "all-MiniLM-L6-v2 embeddings|https://huggingface.co/second-state/All-MiniLM-L6-v2-Embedding-GGUF/resolve/main/all-MiniLM-L6-v2-Q8_0.gguf|all-MiniLM-L6-v2-Q8_0.gguf|~25 MB"
)
# ──────────────────────────────────────────────────────────────────────────────

download_one() {
  local name="$1"
  local url="$2"
  local filename="$3"
  local size_hint="$4"
  local target="$MODEL_DIR/$filename"

  if [[ -f "$target" ]]; then
    echo "[skip] $name already present at $target"
    return 0
  fi

  echo "[download] $name ($size_hint) → $target"

  if command -v curl > /dev/null 2>&1; then
    curl -L --fail --progress-bar -o "$target.partial" "$url"
  elif command -v wget > /dev/null 2>&1; then
    wget --show-progress -O "$target.partial" "$url"
  else
    echo "error: neither curl nor wget found" >&2
    exit 1
  fi

  mv "$target.partial" "$target"
  echo "[done] $name → $target"
}

for entry in "${MODELS[@]}"; do
  IFS='|' read -r name url filename size_hint <<< "$entry"
  download_one "$name" "$url" "$filename" "$size_hint"
done

echo ""
echo "All model weights present in $MODEL_DIR:"
ls -lh "$MODEL_DIR"/*.gguf

# ── Sanity check: primary model path must match metadata.json's _runtime.model_path ──
PRIMARY_MODEL="$MODEL_DIR/qwen2.5-1.5b-instruct-q4_k_m.gguf"
if [[ ! -f "$PRIMARY_MODEL" ]]; then
  echo "error: primary model missing at $PRIMARY_MODEL — check metadata.json _runtime.model_path matches" >&2
  exit 1
fi

echo ""
echo "done."