"""Where requests go. Every target speaks the OpenAI chat-completions API."""

import os

LOCAL_URL = os.environ.get("LOCAL_URL", "http://127.0.0.1:8080/v1")
OPENROUTER_URL = "https://openrouter.ai/api/v1"
OPEN_MODEL = "meta-llama/llama-3.1-8b-instruct"


def _openrouter(provider):
    return {
        "base_url": OPENROUTER_URL,
        "key_env": "OPENROUTER_API_KEY",
        "model": OPEN_MODEL,
        # Pin one provider, no silent fallback: otherwise you are measuring OpenRouter's router, not the provider.
        "extra": {"provider": {"only": [provider], "allow_fallbacks": False}, "usage": {"include": True}},
    }


TARGETS = {
    "local-mac": {"base_url": LOCAL_URL, "key_env": None, "model": "local", "extra": {}},
    "deepinfra": _openrouter("deepinfra"),
    "novita": _openrouter("novita"),
    "groq": _openrouter("groq"),
    "cloudflare": _openrouter("cloudflare"),
    "coreweave": _openrouter("coreweave"),
}
