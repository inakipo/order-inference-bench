# Results

120 synthetic Spanish orders · Llama 3.1 8B Instruct · temperature 0 · via OpenRouter with one provider pinned per run.

## Quality, latency, cost

| Setup | Valid orders | All fields correct | Dates correct | TTFT p50 | Latency p95 | $ / 1k orders |
|---|---|---|---|---|---|---|
| deepinfra · prompt | 95.8% | **65.8%** | 78.3% | 0.42 s | 2.19 s | 0.044 |
| deepinfra · json_schema | rejected by provider | | | | | |
| novita · prompt | 96.7% | **64.2%** | 78.3% | 0.54 s | 1.51 s | 0.045 |
| novita · json_schema | rejected by provider | | | | | |
| groq · prompt | 97.5% | **68.3%** | 80.0% | 0.20 s | 0.47 s | 0.072 |
| groq · json_schema | rejected by provider | | | | | |
| cloudflare · prompt | 97.5% | **63.3%** | 79.2% | 0.75 s | 6.60 s | 0.332 |
| cloudflare · json_schema | rejected by provider | | | | | |
| coreweave · prompt | 98.3% | **60.0%** | 78.3% | 0.32 s | 1.64 s | 0.467 |
| coreweave · json_schema | 96.7% | **57.5%** | 76.7% | 0.31 s | 1.48 s | 0.474 |
| groq · prompt · cal | 99.2% | **84.2%** | 97.5% | 0.21 s | 0.70 s | 0.078 |
| deepinfra · prompt · cal | 95.0% | **73.3%** | 85.8% | 0.37 s | 1.84 s | 0.047 |
| guard(groq->deepinfra) · prompt · guard | 98.3% | **69.2%** | 80.0% | 0.20 s | 0.60 s | 0.071 |
| guard(groq->deepinfra) · prompt · guard+calendar | 100.0% | **84.2%** | 97.5% | 0.21 s | 0.52 s | 0.077 |

![workarounds](workarounds.png)

## Load

| Target | Concurrency | Throughput (tok/s) | Per-user decode (tok/s) | TTFT p50 | TTFT p95 | Latency p95 |
|---|---|---|---|---|---|---|
| deepinfra | 1 | 53.0 | 92.9 | 0.34 s | 0.96 s | 2.02 s |
| deepinfra | 4 | 234.7 | 105.2 | 0.38 s | 0.43 s | 1.19 s |
| deepinfra | 8 | 476.1 | 103.3 | 0.35 s | 0.68 s | 1.38 s |
| deepinfra | 16 | 899.6 | 106.6 | 0.36 s | 0.72 s | 1.43 s |
| deepinfra | 32 | 1492.6 | 97.8 | 0.36 s | 0.7 s | 1.78 s |

| Target | Concurrency | Throughput (tok/s) | Per-user decode (tok/s) | TTFT p50 | TTFT p95 | Latency p95 |
|---|---|---|---|---|---|---|
| groq | 1 | 186.8 | 799.8 | 0.23 s | 0.58 s | 0.67 s |
| groq | 4 | 611.2 | 680.5 | 0.22 s | 0.27 s | 0.54 s |
| groq | 8 | 1315.5 | 531.9 | 0.21 s | 0.28 s | 0.55 s |
| groq | 16 | 2703.9 | 753.4 | 0.23 s | 0.4 s | 0.54 s |
| groq | 32 | 2869.5 | 671.0 | 0.4 s | 0.82 s | 0.99 s |

![load](load_curve.png)
