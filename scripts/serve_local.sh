#!/usr/bin/env bash
# Local OpenAI-compatible server on the Mac GPU (Metal) via llama.cpp.
#   PARALLEL = batch slots (continuous batching across them)
#   CTX      = total KV cache in tokens, split evenly across slots
#   DRAFT=1  = speculative decoding with Llama 3.2 1B as the draft model
set -euo pipefail
MODELS=${MODELS:-$HOME/models}
MODEL=${MODEL:-$MODELS/Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf}
PARALLEL=${PARALLEL:-4}
CTX=${CTX:-12288}
args=(-m "$MODEL" -ngl 99 -c "$CTX" --parallel "$PARALLEL" --port 8080 --host 127.0.0.1 -fa on --metrics)
if [[ "${DRAFT:-0}" == 1 ]]; then
  args+=(-md "$MODELS/Llama-3.2-1B-Instruct-Q8_0.gguf" -ngld 99 --spec-type draft-simple --spec-draft-n-max 8 --spec-draft-n-min 1)
fi
exec llama-server "${args[@]}"
