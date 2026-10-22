#!/bin/bash
# Runs on the pod (vllm/vllm-openai image): baseline evals, LoRA training, fine-tuned evals. One GPU, so strictly sequential.
set -u
cd /workspace/bench/bench
export RUNPOD_POD_URL=http://127.0.0.1:8000/v1 RUNPOD_API_KEY=local
pip install -q peft httpx pydantic >/dev/null 2>&1
pip install -q flash-linear-attention >/dev/null 2>&1 || echo "fla not installed (slower linear attention fallback)"

serve() {  # $1 model path/id, $2 served name
  vllm serve "$1" --served-model-name "$2" --max-model-len 4096 --gpu-memory-utilization 0.90 --enable-prefix-caching --port 8000 > /workspace/vllm_$2.log 2>&1 &
  VPID=$!
  for i in $(seq 1 120); do curl -s localhost:8000/v1/models | grep -q "$2" && { echo "$(date +%T) served $2"; return 0; }; sleep 5; done
  echo "$(date +%T) SERVE FAILED $2"; tail -30 /workspace/vllm_$2.log; return 1
}
evals() {  # $1 served name
  for data in eval.jsonl eval_paraphrased.jsonl; do
    RUNPOD_MODEL=$1 python3 run_eval.py --target runpod-pod --calendar --concurrency 16 --data $data --tag "_${1}_${data%.jsonl}" | tail -25
  done
}
stop() { kill $VPID; wait $VPID 2>/dev/null; sleep 5; }

echo "$(date +%T) START"
serve Qwen/Qwen3.5-4B qwen35-4b-base && evals qwen35-4b-base; stop
echo "$(date +%T) TRAIN START"
python3 /workspace/bench/lora/train_lora.py /workspace/bench/data/train.jsonl /workspace/qwen35-4b-orders 2>&1 | grep -v Warning
echo "$(date +%T) TRAIN END"
serve /workspace/qwen35-4b-orders qwen35-4b-lora && evals qwen35-4b-lora; stop
serve Qwen/Qwen3.5-9B qwen35-9b-base && evals qwen35-9b-base; stop
echo "$(date +%T) ALL DONE"
