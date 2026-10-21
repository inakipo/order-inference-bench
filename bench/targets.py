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


# RunPod (self-hosted vLLM). Both expose the OpenAI API:
#   pod:        https://<POD_ID>-8000.proxy.runpod.net/v1
#   serverless: https://api.runpod.ai/v2/<ENDPOINT_ID>/openai/v1
RUNPOD_MODEL = os.environ.get("RUNPOD_MODEL", "meta-llama/Llama-3.1-8B-Instruct")


def _runpod(url_env):
    return {"base_url": os.environ.get(url_env, ""), "key_env": "RUNPOD_API_KEY", "model": RUNPOD_MODEL, "extra": {}}


TARGETS = {
    "local-mac": {"base_url": LOCAL_URL, "key_env": None, "model": "local", "extra": {}},
    "deepinfra": _openrouter("deepinfra"),
    "novita": _openrouter("novita"),
    "groq": _openrouter("groq"),
    "cloudflare": _openrouter("cloudflare"),
    "coreweave": _openrouter("coreweave"),
    "runpod-pod": _runpod("RUNPOD_POD_URL"),
    "runpod-serverless": _runpod("RUNPOD_SERVERLESS_URL"),
}
