"""Streamlit UI. Run with: streamlit run app.py

A two-panel writing workspace: editable Original on the left, Rewrite on the right.
Colours and the Inter font come from .streamlit/config.toml.
"""
import hashlib
import html
import json
import os
import time

import streamlit as st

from rewriter import (MAX_INPUT_CHARS, MODELS, PROMPTS, STYLES, diff_html, find_numbers, numbers_kept, rewrite,
                      similarity, text_stats)

st.set_page_config(page_title="Text Rewriting & Grammar Assistant", page_icon="✍️", layout="wide")

ACCENT, BORDER, MUTED = "#1F6B4A", "#E4DFD4", "#6B716C"
PANEL_HEIGHT = 330      # height of the text box and the rewrite area, so both panels line up
SHORT_TEXT_WORDS = 30   # below this, readability formulas are not meaningful
EASE, GRADE = "Reading ease (0-100, higher = easier)", "School grade level"

# Demo inputs for "Try an example": each click loads the next one (ids from samples.json).
_samples = {s["id"]: s["text"] for s in json.load(open("samples.json", encoding="utf-8"))}
EXAMPLES = [_samples[i] for i in (2, 1, 5, 3, 8, 7)]

st.markdown(f"""<style>
[data-testid="stHeader"]{{display:none}}
[data-testid="stMainBlockContainer"]{{max-width:1152px;padding:0 16px 16px}}
.topbar{{display:flex;align-items:center;gap:10px;padding:14px 0;border-bottom:1px solid {BORDER};margin-bottom:20px}}
.topbar .mark{{width:30px;height:30px;border-radius:8px;background:{ACCENT};color:#fff;display:flex;
  align-items:center;justify-content:center;font-weight:700;font-size:16px}}
.topbar .name{{font-weight:600;font-size:.98rem}}
.hero h1{{font-size:1.7rem;margin:0;padding:0;line-height:1.25}}
.hero p{{margin:4px 0 4px;color:{MUTED}}}
.st-key-panel_left,.st-key-panel_right{{background:#FFFEFB}}
.st-key-panel_left textarea{{font-size:1.02rem;line-height:1.7}}
.panel-label{{font-weight:600;font-size:.95rem;padding:6px 0}}
.placeholder{{height:{PANEL_HEIGHT}px;display:flex;align-items:center;justify-content:center;color:#8F948F;
  border:1px dashed {BORDER};border-radius:8px;text-align:center;padding:16px}}
.doc{{white-space:pre-wrap;line-height:1.7;font-size:1.02rem;padding:2px 4px}}
.doc del{{background:rgba(196,52,52,.10);color:#9B2C2C;text-decoration:line-through;border-radius:3px;padding:0 2px}}
.doc ins{{background:rgba(31,107,74,.12);color:inherit;text-decoration:none;border-bottom:2px solid {ACCENT};
  border-radius:3px 3px 0 0;padding:0 2px}}
.footer{{text-align:center;color:#8F948F;font-size:.82rem;padding:22px 0 4px;border-top:1px solid {BORDER};margin-top:24px}}
</style>""", unsafe_allow_html=True)


def doc(inner):
    """Already-escaped HTML in the document style."""
    return f'<div class="doc">{inner}</div>'


def copy_button(text, uid):
    """A real 'Copy rewrite' button: copies the clean text and shows 'Copied' for a moment."""
    return f"""
<button id="copy-{uid}" style="font:inherit;font-size:.85rem;font-weight:500;border:1px solid {BORDER};
  background:#fff;color:#1E2320;border-radius:999px;padding:5px 14px;cursor:pointer;white-space:nowrap">
  Copy rewrite</button>
<textarea id="text-{uid}" hidden>{html.escape(text)}</textarea>
<script>
(() => {{
  const root = (document.currentScript && document.currentScript.getRootNode()) || document;
  const btn = root.querySelector("#copy-{uid}"), src = root.querySelector("#text-{uid}");
  if (!btn || btn.dataset.ready) return;
  btn.dataset.ready = "1";
  btn.addEventListener("click", async () => {{
    try {{ await navigator.clipboard.writeText(src.value); }}
    catch (e) {{  // older browsers / no clipboard permission
      const t = document.createElement("textarea"); t.value = src.value; document.body.appendChild(t);
      t.select(); document.execCommand("copy"); t.remove();
    }}
    btn.textContent = "Copied ✓"; btn.style.color = "{ACCENT}"; btn.style.borderColor = "{ACCENT}";
    setTimeout(() => {{ btn.textContent = "Copy rewrite"; btn.style.color = ""; btn.style.borderColor = "{BORDER}"; }}, 1500);
  }});
}})();
</script>"""


def friendly_error(e):
    """Turn an exception into a message a user can act on."""
    msg = str(e)
    if isinstance(e, ValueError):
        return msg
    low = (type(e).__name__ + " " + msg).lower()
    if "auth" in low or "401" in low or "invalid api key" in low:
        return "Groq rejected the API key. Check GROQ_API_KEY in your .env file."
    if "ratelimit" in low or "rate limit" in low or "429" in low:
        return "Groq's free-tier rate limit was reached. Wait about a minute and try again."
    if "connect" in low or "timeout" in low or "timed out" in low:
        return "Could not reach Groq. Check your internet connection and try again."
    return f"The model call failed: {msg[:200]}"


def load_example():
    i = st.session_state.get("example_i", 0)
    st.session_state.draft = EXAMPLES[i % len(EXAMPLES)]
    st.session_state.example_i = i + 1


# --- Header ---
st.html(f"""<div class="topbar"><div class="mark">✎</div>
<div class="name">Text Rewriting &amp; Grammar Assistant</div></div>""")
st.html("""<div class="hero"><h1>Make your writing clearer</h1>
<p>Paste your text, pick one or more styles and click Rewrite. Compare the result side by side.</p></div>""")

# The editor is drawn first on the page but filled in last, because it needs the values from
# "Advanced settings", which sit below it. Streamlit containers can be filled in any order.
editor = st.container()
details = st.container()

with st.expander("Advanced settings", icon=":material/tune:"):
    c1, c2 = st.columns(2, gap="large")
    model = c1.selectbox("Model (Groq)", MODELS)
    prompt = c1.radio("Prompt version", list(PROMPTS), horizontal=True,
                      help="v1 = basic prompt, v2 = improved prompt")
    temperature = c2.slider("Temperature", 0.0, 1.0, 0.3, 0.1,
                            help="Low = safe, consistent edits. High = more creative, more varied.")
    max_tokens = c2.slider("Max tokens", 256, 4096, 2048, 256, help="Upper limit on the output length.")

st.html('<div class="footer">IILM University · CSE2591 · Group 3</div>')

with editor:
    # Toolbar: the four styles and the Rewrite button.
    with st.container(horizontal=True, vertical_alignment="center", horizontal_alignment="distribute"):
        styles = st.pills("Rewrite styles", list(STYLES), selection_mode="multi", key="styles",
                          default=["Grammar Fix", "Formal"], label_visibility="collapsed")
        go = st.button("Rewrite", type="primary", icon=":material/auto_fix_high:", key="go")

    left, right = st.columns(2, gap="medium")

    with left, st.container(border=True, key="panel_left"):
        with st.container(horizontal=True, vertical_alignment="center", horizontal_alignment="distribute"):
            st.html('<div class="panel-label">Original</div>', width="content")
            st.button("Try an example", on_click=load_example, type="tertiary", icon=":material/lightbulb:")
        text = st.text_area("Original", key="draft", height=PANEL_HEIGHT, label_visibility="collapsed",
                            placeholder="Paste or type the text you want to improve...")
        words = len(text.split())
        st.caption(f"{words} word{'' if words == 1 else 's'} · {len(text)} / {MAX_INPUT_CHARS} characters")

    with right, st.container(border=True, key="panel_right"):
        st.html('<div class="panel-label">Rewrite</div>')

        # Streamlit reruns this whole script on every click, so the last result is kept in session_state.
        if go:
            if not text.strip():
                st.session_state.last = {"error": "Please enter some text first, or click **Try an example**."}
            elif not styles:
                st.session_state.last = {"error": "Pick at least one rewrite style above."}
            else:
                results = {}
                for style in styles:
                    start = time.time()
                    try:
                        with st.spinner(f"Rewriting ({style})..."):
                            results[style] = {"text": rewrite(text, style, prompt, model, temperature, max_tokens)}
                    except Exception as e:  # too long, bad key, rate limit, network
                        results[style] = {"error": friendly_error(e)}
                    results[style]["seconds"] = round(time.time() - start, 1)
                st.session_state.last = {"text": text, "results": results, "model": model, "prompt": prompt,
                                         "temperature": temperature, "max_tokens": max_tokens}

        last = st.session_state.get("last")
        if not last:
            st.html('<div class="placeholder">Your rewrite will appear here.</div>')
        elif "error" in last:
            st.error(last["error"], icon=":material/error:")
            st.caption("Your draft is kept.")
        else:
            if last["text"] != text:
                st.caption(":material/info: This is the rewrite of your previous text. Click **Rewrite** to update it.")
            results = last["results"]
            areas = st.tabs(list(results)) if len(results) > 1 else [st.container()]
            for area, (style, res) in zip(areas, results.items()):
                with area:
                    if "error" in res:
                        st.error(f"{style}: {res['error']}", icon=":material/error:")
                        st.caption("Your draft is kept. Try again.")
                        continue
                    with st.container(horizontal=True, vertical_alignment="center",
                                      horizontal_alignment="distribute"):
                        show_changes = st.toggle("Show changes", key=f"changes_{style}",
                                                 help="Red = removed, green = added")
                        uid = hashlib.md5(f"{style}{res['text']}".encode()).hexdigest()[:10]
                        st.html(copy_button(res["text"], uid), width="content", unsafe_allow_javascript=True)
                    with st.container(height=PANEL_HEIGHT - (90 if len(results) > 1 else 44), border=False):
                        # diff_html and html.escape both escape the text, so nothing in it can inject HTML
                        st.html(doc(diff_html(last["text"], res["text"]) if show_changes
                                    else html.escape(res["text"])))

# --- Comparison details: metrics, full table, generation details (collapsed) ---
last = st.session_state.get("last")
done = {s: r for s, r in (last or {}).get("results", {}).items() if "text" in r}
if done:
    with details, st.expander("Comparison details", icon=":material/analytics:"):
        original = last["text"]
        st.caption(f"Generated with {last['model']} · prompt {last['prompt']} · temperature {last['temperature']} "
                   f"· max tokens {last['max_tokens']}")
        areas = st.tabs(list(done)) if len(done) > 1 else [st.container()]
        for area, (style, res) in zip(areas, done.items()):
            with area:
                result = res["text"]
                before, after = text_stats(original), text_stats(result)
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Words kept (similarity)", f"{similarity(original, result):.0%}", border=True,
                          help="Share of words kept in order. Low = heavy rewrite, so check the meaning.")
                if find_numbers(original):
                    c2.metric("All numbers kept?", "Yes" if numbers_kept(original, result) else "No — check!",
                              border=True, help="Every number, date and time must still be in the rewrite.")
                else:
                    c2.metric("All numbers kept?", "No numbers in original", border=True)
                c3.metric("Reading ease", after[EASE], f"{after[EASE] - before[EASE]:+.1f}", border=True,
                          help="0-100, higher = easier.")
                c4.metric("Grade level", after[GRADE], f"{after[GRADE] - before[GRADE]:+.1f}",
                          delta_color="inverse", border=True, help="School grade needed to read it. Lower = easier.")
                if min(before["Words"], after["Words"]) < SHORT_TEXT_WORDS:
                    st.caption(f":material/info: The text is short (under {SHORT_TEXT_WORDS} words), "
                               "so the readability scores are only rough.")
                st.table({"Original": {k: str(v) for k, v in before.items()},  # str: avoid "13.0000"
                          "Rewritten": {k: str(v) for k, v in after.items()}})
                st.caption(f"Generated in {res['seconds']} s. Reading ease and grade level use English "
                           "formulas, so they are not reliable for mixed-language text such as Hinglish.")
                if original.strip() != text.strip():
                    st.caption("Submitted original:")
                    st.html(doc(html.escape(original)))

if not os.getenv("GROQ_API_KEY"):
    with editor:
        st.error("GROQ_API_KEY not found. Copy .env.example to .env and paste your key from console.groq.com.")
