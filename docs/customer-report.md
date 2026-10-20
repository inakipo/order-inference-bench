# Order extraction on open models: recommendation

**For:** a Spanish gourmet distributor's operations team (fictional customer, real workload shape)
**Workload:** incoming orders (email, WhatsApp, voice notes) to structured orders, ~2,000 prompt tokens per order (catalog + rules)

## Recommendation
Run **Llama 3.1 8B on Groq**, with two small pieces of our code in front of it:
1. **A date calendar computed in code** and passed with each message, so the model never does date arithmetic.
2. **A schema guard**: validate every answer, give the model one chance to fix it with the exact error, and fall back to
   a second provider (DeepInfra) if it still fails.

| | Today, prompt only | Recommended setup |
|---|---|---|
| Orders with every field right | 68% | **84%** |
| Orders that parse and match the catalog | 97.5% | **100%** |
| Delivery dates right | 80% | **97.5%** |
| Latency, 95th percentile | 0.47 s | 0.52 s |
| Cost per 1,000 orders | $0.07 | $0.08 |

## What to know before go-live
- **16% of orders still have one field wrong**, mostly orders with corrections ("better 6 instead of 20"). Keep a human
  check on orders where the customer corrected themselves, or test a larger model on those cases only.
- **Don't switch on the provider's "JSON schema" mode.** On the one provider that supports it for this model, it corrupted
  accented names (Mesón, Peñalta) in 32 of 38 cases. The guard gives the same guarantee without that bug.
- **Capacity:** Groq held ~2,400 orders per minute at 16 concurrent requests in our test; latency doubles past that, so
  peaks above that need a second provider or a queue.
- **Keep the prompt start stable** (catalog first, today's date last). Groq reuses the cached prefix: faster and cheaper.

## Next step
Run the same eval on 200 of your real orders (anonymised) before go-live. That's one day, and it replaces our synthetic numbers with yours.
