# Text Rewriting and Grammar Assistant

CSE2591 Generative AI for Development, Mini Project, Group 3
Sushri Sangita Swain (2481027) · Punit (2481019) · Nisha (2481159)

A web app that rewrites text for clarity, grammar and readability in 4 styles (Grammar Fix, Formal, Simple, Concise) and compares the original with the rewrite: side by side, a highlighted word diff, and readability scores.

**Stack:** Python · Streamlit (UI) · LangChain (prompt pipeline) · Groq API with GPT-OSS 120B (LLM) · textstat (readability) · difflib (diff)

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # then paste your free key from console.groq.com/keys
```

## Run

```bash
streamlit run app.py      # the app, opens in the browser
python test_rewriter.py   # offline checks, no API key needed
python evaluate.py        # tests v1 vs v2 prompts on samples.json, writes results.csv
```

## Files

| File | What it does |
|---|---|
| `rewriter.py` | Prompts, LLM call, comparison metrics (the core) |
| `app.py` | Streamlit web interface |
| `evaluate.py` | Batch testing for the report |
| `samples.json` | 8 test inputs, including tricky ones |
| `test_rewriter.py` | Offline self-checks |
| `results.csv` | Final test results (prompt v1 vs v2) |
| `results_run1.csv` | First test run, before the prompt fix |

The `.env` file holds the API key and is never committed or submitted.
