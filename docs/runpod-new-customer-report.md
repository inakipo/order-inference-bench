# Runpod as a new customer: one day, one workload

**Workload:** Spanish B2B order extraction (the same 120-order eval as the rest of this repo), served with vLLM 0.32.0 on Runpod,
first as a pod, then as serverless. Everything below was run by me on 2026-10-22 with a fresh account and $10 of credit; total
spend was **$1.68**. Raw numbers: [`results/cold_start_cache_volume.json`](../results/cold_start_cache_volume.json),
[`results/summary.jsonl`](../results/summary.jsonl), [`results/lora/`](../results/lora/).

## Headline

**Serverless cold start on a cache volume: 4:37 → 2:31 with two environment variables.** With `HF_HOME` and `VLLM_CACHE_ROOT` on a
network volume, the vLLM worker reuses the torch.compile graph but not the Triton kernels it points to: those are cached under
`/tmp/torchinductor_root`, so every new worker logs `Cubin file saved by TritonBundler not found` and rebuilds them during warm-up.

```
TORCHINDUCTOR_CACHE_DIR=/runpod-volume/vllm-cache/inductor
TRITON_CACHE_DIR=/runpod-volume/vllm-cache/triton
```

| Qwen3.5-9B FP8, L40S, EU-NL-1 | GPU assigned to first answer | torch.compile | warm-up | engine init |
|---|---|---|---|---|
| empty volume | ~440 s | | | |
| filled volume, default env | 277 s | 2.9 s | 78.9 s | 136 s |
| filled volume + the two variables | **151 s** | 1.8 s | **1.6 s** | **48 s** |

What is left after the fix: ~40 s Python and engine start, ~40 s reading weights from the network volume, ~25 s CUDA graph capture.

## Pod vs serverless (Qwen3.5-9B FP8 on a 4090)

| | Result |
|---|---|
| Accuracy | 77.5% of orders fully right, 80.0% with dates resolved in code; 100% valid JSON |
| Throughput | 1 user: 45 orders/min, TTFT 0.31 s. 32 users: 618 orders/min, p95 latency 4.3 s, 0 errors |
| Pod cost | $0.89/h = $0.024 per 1k orders at full load; beats the cheapest API ($0.044/1k) only above ~20k orders/h |
| Serverless | idle $0/h; warm 1.3 to 1.5 s; first request on a new endpoint 508 s; cold after 60 s idle: 1.6 s once (FlashBoot), 215 to 220 s twice |

## Friction log (what a new customer trips on)

1. The vLLM template defaults to an 8 GB container disk for an ~18 GB model; only a soft warning.
2. GPU preference order ignored on pod create (asked A40/A5000, placed on a 4090); a fourth GPU type was added to a serverless endpoint without being asked for.
3. A crash loop (bf16 9B on 24 GB) is visible only in logs; the REST API has no logs (`runpodctl` does), and serverless logs are gone once a worker scales down.
4. Serverless banner: "100% of your max workers are busy" while 0 workers were running.
5. A queued request on the OpenAI-compatible route returns an **HTML 504 after ~10 min** while the job stays queued; a client that retries creates duplicate jobs (we ended up with 3 queued for 1 request).
6. `PATCH workersMax=1` returns success, but requests keep getting `409 ENDPOINT_PAUSED` for 20+ s.
7. A network volume pins the endpoint to one data centre. For L40S that was EU-NL-1 only; GPU waits were **20, 3, 42 and 6.5 min**, and the console's advice ("edit GPU configuration") does not mention the volume is the constraint.
8. Pod with a pinned image tag (`vllm/vllm-openai:v0.32.0`) showed RUNNING for 22 min with no container, no logs and no IP. The same version via `:latest` started in 24 s (cached on the host). Pinning, the best practice, is punished and nothing says why.

## Top 3 fixes, in order

1. **Make the cache volume work by default in the vLLM worker**: when `/runpod-volume` is mounted, put the Inductor and Triton caches under `VLLM_CACHE_ROOT`. Measured 4:37 → 2:31; a few lines in the worker.
2. **Be explicit about capacity**: show that a volume pins the data centre, show expected queue time per GPU and DC, honour the GPU preference order, and explain "throttled".
3. **Errors a client can act on**: JSON (with the job id and "still queued") instead of an HTML 504; worker logs in the API and kept after scale-down; image-pull progress on pods.

## Bonus: a LoRA on Runpod

LoRA (r=16, 30M trainable params, 0.67%) on Qwen3.5-4B, 1,500 synthetic orders disjoint from the eval, 47 min on one A40 ($0.59/h),
merged and served with vLLM on the same pod. Second test set: the 120 eval orders rewritten by a different model (gpt-oss-120b)
with the same facts; 114 kept after a fact check.

| same A40, vLLM bf16, dates in code | original orders | rewritten orders | p50 latency |
|---|---|---|---|
| Qwen3.5-4B, prompt only | 69.2% | 67.5% | 2.1 s |
| Qwen3.5-9B, prompt only | 78.3% | 86.8% | 3.4 s |
| **Qwen3.5-4B + LoRA** | **98.3%** | **95.6%** | **2.0 s** |

Remaining misses are pack sizes ("una caja con seis botellas" read as 6). Caveat: both sets are synthetic; the next test is a few
hundred real customer messages.

Reproduce: `bench/make_train.py`, `bench/make_paraphrased.py`, `lora/train_lora.py`, `lora/run_all.sh`.
