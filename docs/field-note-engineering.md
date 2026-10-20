# Field note: structured output for small open models in EMEA

**From:** a customer deployment (order extraction, Spanish) · **Model:** Llama 3.1 8B Instruct · **Date:** 2026-10-20

## What the customer hit
1. **Schema enforcement mostly isn't there.** 4 of 5 providers serving Llama 3.1 8B rejected `response_format: json_schema`:
   three "not supported for this model" (one offers only `json_object`), one "not supported with stream mode". A
   customer moving from a closed API, where strict schemas are table stakes, hits this on day one.
2. **Where it exists, it breaks non-English text.** With the schema on, 32 of 38 outputs containing an accented customer
   name or city came back with control characters in place of the accented letter (`Mesón` → `Mes\u0004on`,
   `Peñalta` → `Pe\u0014alta`). Same provider without the schema: 0 of 38; non-accented orders: 0. Likely the
   grammar mask handling multi-byte UTF-8 tokens. 4/120 runs also looped inside a string until max_tokens. English-only
   test suites will not see this; every Spanish, French, German or Portuguese customer will.
3. **Prefix caching is invisible to the customer.** Two providers reported ~1.5k cached tokens per request on an identical
   prefix; three reported none. Customers with agent workloads (long, stable system prompts) cannot tell in advance
   which they get, and it changes both latency and cost.

## What I built so the customer could ship anyway
A ~100-line schema guard (validate → one repair turn → cross-provider fallback), exposed as an OpenAI-compatible proxy:
100% valid orders with no p95 penalty (0.52 s). Plus resolving relative dates in code: +17 points on dates.

## Ask
- Ship strict JSON-schema decoding for the popular small open models, **with a non-ASCII test set** (accents, ñ, ß, ç)
  in its CI. Smallest repro: schema with one `string` field, input containing "Peñalta", temperature 0.
- Report `cached_tokens` in usage on every model, and document the prefix-cache behaviour.
- Until then, a documented "validate + repair" helper in the SDK would close most of the gap: it's the workaround every
  FDE will otherwise rebuild per customer.
