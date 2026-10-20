"""Build results/REPORT.md tables and charts from the result files."""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).parent.parent
RES = ROOT / "results"
plt.rcParams.update({"font.size": 11, "axes.spines.top": False, "axes.spines.right": False, "figure.dpi": 150})
COLORS = {"groq": "#e4572e", "deepinfra": "#4c6ef5", "novita": "#2fb380", "cloudflare": "#f59f00", "coreweave": "#7950f2"}


def latest_summaries():
    rows = {}
    for line in (RES / "summary.jsonl").open():
        s = json.loads(line)
        rows[(s["target"], s["mode"], s.get("tag", ""))] = s  # last run wins
    return list(rows.values())


def fmt(v, nd=2):
    return "–" if v is None else (f"{v:.{nd}f}" if isinstance(v, float) else str(v))


def table(rows):
    head = "| Setup | Valid orders | All fields correct | Dates correct | TTFT p50 | Latency p95 | $ / 1k orders |\n|---|---|---|---|---|---|---|\n"
    body = ""
    for s in rows:
        name = f"{s['target']} · {s['mode']}{(' · ' + s['tag'].strip('_')) if s.get('tag') else ''}"
        if s["errors"] == s["n"]:
            body += f"| {name} | rejected by provider | | | | | |\n"
            continue
        body += (f"| {name} | {s['valid_order_%']}% | **{s['all_fields_correct_%']}%** | {s['date_%']}% | {fmt(s['ttft_p50_s'])} s "
                 f"| {fmt(s['latency_p95_s'])} s | {fmt(s['usd_per_1k_orders'], 3)} |\n")
    return head + body


def load_chart():
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4))
    for f in sorted(RES.glob("load_*.jsonl")):
        rows = [json.loads(line) for line in f.open()]
        t = rows[0]["target"]
        x = [r["concurrency"] for r in rows]
        c = COLORS.get(t, "#555")
        a1.plot(x, [r["throughput_out_tok_s"] for r in rows], "o-", color=c, label=t)
        a2.plot(x, [r["ttft_p95_s"] for r in rows], "o-", color=c, label=t)
    a1.set(title="Total output throughput", xlabel="concurrent requests", ylabel="tokens / s", xscale="log", xticks=[1, 4, 8, 16, 32])
    a2.set(title="Time to first token, p95", xlabel="concurrent requests", ylabel="seconds", xscale="log", xticks=[1, 4, 8, 16, 32])
    for a in (a1, a2):
        a.get_xaxis().set_major_formatter(matplotlib.ticker.ScalarFormatter())
        a.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(RES / "load_curve.png")


def workaround_chart(rows):
    pick = [("groq", "prompt", ""), ("groq", "prompt", "_cal"), ("guard(groq->deepinfra)", "prompt", "guard+calendar")]
    labels = ["Groq, prompt only", "+ calendar in code", "+ schema guard"]
    by = {(s["target"], s["mode"], s.get("tag", "")): s for s in rows}
    vals = [by[k] for k in pick if k in by]
    fig, ax = plt.subplots(figsize=(8, 3.6))
    x = range(len(vals))
    ax.bar([i - 0.2 for i in x], [v["valid_order_%"] for v in vals], 0.4, label="valid orders", color="#adb5bd")
    ax.bar([i + 0.2 for i in x], [v["all_fields_correct_%"] for v in vals], 0.4, label="all fields correct", color="#4c6ef5")
    for i, v in enumerate(vals):
        ax.text(i + 0.2, v["all_fields_correct_%"] + 1, f"{v['all_fields_correct_%']:.0f}%", ha="center")
    ax.set_xticks(list(x), labels[: len(vals)])
    ax.set(ylim=(0, 125), ylabel="% of 120 orders", title="Llama 3.1 8B on Spanish orders: what the workarounds buy")
    ax.legend(frameon=False, loc="upper center", ncol=2)
    fig.tight_layout()
    fig.savefig(RES / "workarounds.png")


def main():
    rows = latest_summaries()
    load_chart()
    workaround_chart(rows)
    load_md = ""
    for f in sorted(RES.glob("load_*.jsonl")):
        load_md += "\n| Target | Concurrency | Throughput (tok/s) | Per-user decode (tok/s) | TTFT p50 | TTFT p95 | Latency p95 |\n|---|---|---|---|---|---|---|\n"
        for r in map(json.loads, f.open()):
            load_md += (f"| {r['target']} | {r['concurrency']} | {r['throughput_out_tok_s']} | {r['per_user_decode_tok_s_p50']} | "
                        f"{r['ttft_p50_s']} s | {r['ttft_p95_s']} s | {r['latency_p95_s']} s |\n")
    (RES / "REPORT.md").write_text(
        "# Results\n\n120 synthetic Spanish orders · Llama 3.1 8B Instruct · temperature 0 · via OpenRouter with one provider pinned per run.\n\n"
        "## Quality, latency, cost\n\n" + table(rows) +
        "\n![workarounds](workarounds.png)\n\n## Load\n" + load_md + "\n![load](load_curve.png)\n")
    print((RES / "REPORT.md").read_text())


if __name__ == "__main__":
    main()
