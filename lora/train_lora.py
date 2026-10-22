"""LoRA fine-tune of Qwen3.5-4B on the order-extraction task (text only), then merge into a plain checkpoint vLLM can serve.
Loss is computed on the assistant answer only; the system prompt + message are context."""
import json
import os
import shutil
import sys
import time

import torch
from huggingface_hub import snapshot_download
from peft import LoraConfig, get_peft_model
from transformers import AutoModelForImageTextToText, AutoTokenizer, get_cosine_schedule_with_warmup

BASE = os.environ.get("BASE", "Qwen/Qwen3.5-4B")
DATA, OUT = sys.argv[1], sys.argv[2]
EPOCHS, LR, ACCUM, RANK = float(os.environ.get("EPOCHS", 1)), float(os.environ.get("LR", 2e-4)), 16, 16
TARGETS = r".*language_model\.layers\.\d+\.(self_attn\.(q|k|v|o)_proj|linear_attn\.(in_proj_qkv|in_proj_z|out_proj)|mlp\.(gate|up|down)_proj)"

tok = AutoTokenizer.from_pretrained(BASE)
model = AutoModelForImageTextToText.from_pretrained(BASE, dtype=torch.bfloat16, device_map="cuda")
model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
model.enable_input_require_grads()
model = get_peft_model(model, LoraConfig(r=RANK, lora_alpha=2 * RANK, lora_dropout=0.0, target_modules=TARGETS, task_type="CAUSAL_LM"))
model.print_trainable_parameters()


def encode(row):
    msgs = row["messages"]
    kw = {"tokenize": False, "enable_thinking": False}
    prompt = tok.apply_chat_template(msgs[:-1], add_generation_prompt=True, **kw)
    full = prompt + msgs[-1]["content"] + "<|im_end|>\n"
    p_ids = tok(prompt, add_special_tokens=False)["input_ids"]
    ids = tok(full, add_special_tokens=False)["input_ids"]
    labels = [-100] * len(p_ids) + ids[len(p_ids):]
    return torch.tensor([ids]), torch.tensor([labels])


rows = [json.loads(l) for l in open(DATA)]
steps = int(len(rows) * EPOCHS)
opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=LR, weight_decay=0.0)
sched = get_cosine_schedule_with_warmup(opt, num_warmup_steps=max(1, steps // ACCUM // 20), num_training_steps=max(1, steps // ACCUM))
model.train()
t0, run_loss, n_tok = time.time(), 0.0, 0
log = open(os.path.join(os.path.dirname(OUT) or ".", "train_log.jsonl"), "w")
for step in range(steps):
    ids, labels = encode(rows[step % len(rows)])
    ids, labels = ids.cuda(), labels.cuda()
    loss = model(input_ids=ids, labels=labels).loss / ACCUM
    loss.backward()
    run_loss += loss.item(); n_tok += ids.shape[1]
    if (step + 1) % ACCUM == 0:
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step(); sched.step(); opt.zero_grad(set_to_none=True)
        rec = {"step": (step + 1) // ACCUM, "examples": step + 1, "loss": round(run_loss, 4), "lr": sched.get_last_lr()[0],
               "elapsed_s": round(time.time() - t0, 1), "tok_per_s": round(n_tok / (time.time() - t0))}
        print(json.dumps(rec), flush=True); log.write(json.dumps(rec) + "\n"); log.flush()
        run_loss = 0.0
print(f"TRAIN DONE in {time.time() - t0:.0f}s, peak mem {torch.cuda.max_memory_allocated() / 2**30:.1f} GiB", flush=True)

model.save_pretrained(OUT + "-adapter")
merged = model.merge_and_unload()
merged.save_pretrained(OUT, safe_serialization=True)
tok.save_pretrained(OUT)
src = snapshot_download(BASE)
for f in os.listdir(src):   # processor / chat-template files vLLM expects next to the weights
    if not f.endswith(".safetensors") and f != "model.safetensors.index.json" and not os.path.exists(os.path.join(OUT, f)):
        shutil.copy(os.path.join(src, f), OUT)
print("MERGED", OUT, flush=True)
