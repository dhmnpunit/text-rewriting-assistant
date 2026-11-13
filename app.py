"""Streamlit UI. Run with: streamlit run app.py"""
import html
import os

import streamlit as st

from rewriter import MODELS, PROMPTS, STYLES, diff_html, numbers_kept, rewrite, similarity, text_stats

st.set_page_config(page_title="Text Rewriting & Grammar Assistant", layout="wide")
DIFF_CSS = "<style>del{background:#ffd6d6;color:#a00} ins{background:#d6ffd6;color:#060;text-decoration:none}</style>"


def show_plain(container, text):
    """Show text exactly as typed: no Markdown (so * # _ stay as they are), line breaks kept."""
    container.html(f'<div style="white-space:pre-wrap">{html.escape(text)}</div>')


st.title("✍️ Text Rewriting & Grammar Assistant")
st.caption("AI suggestions can be wrong. Always read the rewrite and check that the meaning is unchanged.")

# --- Sidebar: model settings (these are the parameters asked about in the viva) ---
with st.sidebar:
    st.header("Settings")
    model = st.selectbox("Model (Groq)", MODELS)
    prompt = st.radio("Prompt version", list(PROMPTS), help="v1 = basic prompt, v2 = improved prompt")
    temperature = st.slider("Temperature", 0.0, 1.0, 0.3, 0.1,
                            help="Low = safe, consistent edits. High = more creative, more varied.")
    max_tokens = st.slider("Max tokens", 256, 4096, 2048, 256, help="Upper limit on the output length.")

if not os.getenv("GROQ_API_KEY"):
    st.error("GROQ_API_KEY not found. Copy .env.example to .env and paste your key from console.groq.com.")
    st.stop()

# --- Input ---
text = st.text_area("Your text", height=180, placeholder="Paste or type the text you want to improve...")
styles = st.multiselect("Rewrite styles (pick one or more)", list(STYLES), default=["Grammar Fix", "Formal"])

# Streamlit reruns this whole script on every click or slider move, so the results are kept in
# session_state. Without this they would disappear as soon as any setting is touched.
if st.button("Rewrite", type="primary"):
    if not styles:
        st.warning("Pick at least one style.")
        st.stop()
    results = {}
    for style in styles:
        try:
            with st.spinner(f"Rewriting ({style})..."):
                results[style] = rewrite(text, style, prompt, model, temperature, max_tokens)
        except Exception as e:  # empty input, too long, bad key, rate limit, network
            results[style] = e
    st.session_state.last = {"text": text, "results": results, "settings": f"{model} · prompt {prompt} · "
                             f"temperature {temperature} · max tokens {max_tokens}"}

last = st.session_state.get("last")
if last:
    original = last["text"]
    if original != text:
        st.info("Showing the results for the previous text. Click **Rewrite** to update them.")
    st.caption(f"Generated with: {last['settings']}")

    for tab, (style, result) in zip(st.tabs(list(last["results"])), last["results"].items()):
        with tab:
            if isinstance(result, Exception):
                st.error(f"Could not rewrite: {result}")
                continue

            left, right = st.columns(2)
            left.subheader("Original")
            show_plain(left, original)
            right.subheader(f"Rewritten — {style}")
            show_plain(right, result)

            st.subheader("Changes")
            st.html(DIFF_CSS + diff_html(original, result))  # safe: diff_html escapes all text; html avoids Markdown

            st.subheader("Comparison")
            before, after = text_stats(original), text_stats(result)
            st.table({"Original": {k: str(v) for k, v in before.items()},  # str: avoid "13.0000"
                      "Rewritten": {k: str(v) for k, v in after.items()}})
            st.caption("Reading ease and grade level use English formulas, so they are not reliable "
                       "for mixed-language text such as Hinglish.")
            c1, c2 = st.columns(2)
            c1.metric("Words kept (similarity)", f"{similarity(original, result):.0%}")
            c2.metric("All numbers kept?", "Yes" if numbers_kept(original, result) else "No — check!")
