"""Testing: run every sample through prompt v1 and v2 and save the numbers for the report.

Run with: python evaluate.py   -> prints a summary and writes results.csv
"""
import csv
import json
import time

from rewriter import PROMPTS, numbers_kept, rewrite, similarity, text_stats

STYLES_TO_TEST = ["Grammar Fix", "Formal", "Simple"]
PREAMBLES = ("here is", "here's", "sure", "rewritten", "certainly")

samples = json.load(open("samples.json", encoding="utf-8"))
rows = []
for s in samples:
    for style in STYLES_TO_TEST:
        for prompt in PROMPTS:
            out = rewrite(s["text"], style, prompt, temperature=0.3)
            rows.append({
                "id": s["id"], "type": s["type"], "style": style, "prompt": prompt,
                "similarity": similarity(s["text"], out),
                "reading_ease_before": text_stats(s["text"])["Reading ease (0-100, higher = easier)"],
                "reading_ease_after": text_stats(out)["Reading ease (0-100, higher = easier)"],
                "numbers_kept": numbers_kept(s["text"], out),
                "length_ratio": round(len(out.split()) / len(s["text"].split()), 2),
                "format_problem": out.lower().startswith(PREAMBLES) or out.startswith(('"', "Subject:")) or "**" in out,
                "output": out,
                "meaning_ok (fill manually)": "",
            })
            print(f"#{s['id']} {style:<11} {prompt:<14} -> {out[:70]!r}")
            time.sleep(2)  # ponytail: fixed pause to stay under Groq free-tier rate limits

with open("results.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)

print("\nSummary (paste into report):")
print("| Prompt | Runs | Format problems | Numbers kept | Avg similarity | Avg length ratio | Avg reading ease change |")
print("|---|---|---|---|---|---|---|")
for prompt in PROMPTS:
    r = [x for x in rows if x["prompt"] == prompt]
    print(f"| {prompt} | {len(r)} | {sum(x['format_problem'] for x in r)} "
          f"| {sum(x['numbers_kept'] for x in r)}/{len(r)} "
          f"| {sum(x['similarity'] for x in r) / len(r):.2f} "
          f"| {sum(x['length_ratio'] for x in r) / len(r):.2f} "
          f"| {sum(x['reading_ease_after'] - x['reading_ease_before'] for x in r) / len(r):+.1f} |")
print("\nSaved every output to results.csv. Fill the 'meaning_ok' column by reading each row.")
