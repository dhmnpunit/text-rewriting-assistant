"""Testing: run every sample through prompt v1 and v2 and save the numbers for the report.

Run with: python evaluate.py              -> prints a summary and writes results.csv
          python evaluate.py --out x.csv  -> writes somewhere else (keeps results.csv untouched)
"""
import argparse
import csv
import json
import os
import sys
import time

from rewriter import PROMPTS, STYLES, numbers_kept, rewrite, similarity, text_stats

STYLES_TO_TEST = list(STYLES)  # all 4 styles
PREAMBLES = ("here is", "here's", "sure", "rewritten", "certainly")
MANUAL_COL = "meaning_ok (fill manually)"
EASE = "Reading ease (0-100, higher = easier)"
RETRIES = 4

parser = argparse.ArgumentParser()
parser.add_argument("--out", default="results.csv", help="output CSV file (default: results.csv)")
parser.add_argument("--force", action="store_true", help="overwrite even if the manual column is filled")
args = parser.parse_args()

# Never silently wipe the hand-filled meaning_ok column.
if os.path.exists(args.out) and not args.force:
    with open(args.out, encoding="utf-8") as f:
        if any(r.get(MANUAL_COL, "").strip() for r in csv.DictReader(f)):
            sys.exit(f"{args.out} already has manual '{MANUAL_COL}' entries. "
                     f"Use --out new_results.csv to write a new file, or --force to overwrite.")


def rewrite_with_retry(text, style, prompt):
    """Groq's free tier sometimes rate-limits (429) or times out: wait longer each time and try again."""
    for attempt in range(1, RETRIES + 1):
        try:
            return rewrite(text, style, prompt, temperature=0.3)
        except Exception as e:
            if attempt == RETRIES:
                raise
            wait = 5 * 2 ** (attempt - 1)  # 5, 10, 20 seconds
            print(f"   error ({e.__class__.__name__}: {str(e)[:80]}), retrying in {wait}s...")
            time.sleep(wait)


samples = json.load(open("samples.json", encoding="utf-8"))
fields = ["id", "type", "style", "prompt", "similarity", "reading_ease_before", "reading_ease_after",
          "numbers_kept", "length_ratio", "format_problem", "output", MANUAL_COL]
partial = args.out + ".partial"  # rows are saved here as they arrive, so a crash loses nothing
rows = []
with open(partial, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    for s in samples:
        for style in STYLES_TO_TEST:
            for prompt in PROMPTS:
                try:
                    out = rewrite_with_retry(s["text"], style, prompt)
                except Exception as e:
                    sys.exit(f"\nStopped at #{s['id']} {style} {prompt}: {e}\n"
                             f"The {len(rows)} finished rows are saved in {partial}.")
                row = {
                    "id": s["id"], "type": s["type"], "style": style, "prompt": prompt,
                    "similarity": similarity(s["text"], out),
                    "reading_ease_before": text_stats(s["text"])[EASE],
                    "reading_ease_after": text_stats(out)[EASE],
                    "numbers_kept": numbers_kept(s["text"], out),
                    "length_ratio": round(len(out.split()) / len(s["text"].split()), 2),
                    "format_problem": out.lower().startswith(PREAMBLES) or out.startswith(('"', "Subject:")) or "**" in out,
                    "output": out,
                    MANUAL_COL: "",
                }
                rows.append(row)
                writer.writerow(row)
                f.flush()
                print(f"#{s['id']} {style:<11} {prompt:<14} -> {out[:70]!r}")
                time.sleep(2)  # fixed pause to stay under Groq free-tier rate limits
os.replace(partial, args.out)


def avg(values):
    return sum(values) / len(values)


print("\nSummary (paste into report):")
print("| Prompt | Runs | Format problems | Numbers kept | Avg similarity | Avg length ratio |")
print("|---|---|---|---|---|---|")
for prompt in PROMPTS:
    r = [x for x in rows if x["prompt"] == prompt]
    print(f"| {prompt} | {len(r)} | {sum(x['format_problem'] for x in r)} "
          f"| {sum(x['numbers_kept'] for x in r)}/{len(r)} "
          f"| {avg([x['similarity'] for x in r]):.2f} "
          f"| {avg([x['length_ratio'] for x in r]):.2f} |")

# Per style, because the styles pull in opposite directions (Formal lowers reading ease, Simple raises it),
# so one average over all styles would hide what each style is doing.
print("\nPer style (sample #7 is Hinglish, so its reading ease is left out: the formula is English-only):")
print("| Style | Prompt | Avg similarity | Avg length ratio | Avg reading ease change |")
print("|---|---|---|---|---|")
for style in STYLES_TO_TEST:
    for prompt in PROMPTS:
        r = [x for x in rows if x["style"] == style and x["prompt"] == prompt]
        english = [x for x in r if "Hinglish" not in x["type"]]
        print(f"| {style} | {prompt} | {avg([x['similarity'] for x in r]):.2f} "
              f"| {avg([x['length_ratio'] for x in r]):.2f} "
              f"| {avg([x['reading_ease_after'] - x['reading_ease_before'] for x in english]):+.1f} |")
print(f"\nSaved every output to {args.out}. Fill the '{MANUAL_COL}' column by reading each row.")
