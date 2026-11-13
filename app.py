"""Streamlit UI. Run with: streamlit run app.py"""
import os

import streamlit as st

from rewriter import MODELS, PROMPTS, STYLES, diff_html, numbers_kept, rewrite, similarity, text_stats

st.set_page_config(page_title="Text Rewriting & Grammar Assistant", layout="wide")
st.markdown(
    "<style>del{background:#ffd6d6;color:#a00} ins{background:#d6ffd6;color:#060;text-decoration:none}</style>",
    unsafe_allow_html=True,
)

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

if st.button("Rewrite", type="primary"):
    if not styles:
        st.warning("Pick at least one style.")
        st.stop()

    for tab, style in zip(st.tabs(styles), styles):
        with tab:
            try:
                with st.spinner(f"Rewriting ({style})..."):
                    result = rewrite(text, style, prompt, model, temperature, max_tokens)
            except Exception as e:  # empty input, too long, bad key, rate limit, network
                st.error(f"Could not rewrite: {e}")
                continue

            left, right = st.columns(2)
            left.subheader("Original")
            left.write(text)
            right.subheader(f"Rewritten — {style}")
            right.write(result)

            st.subheader("Changes")
            st.markdown(diff_html(text, result), unsafe_allow_html=True)  # safe: diff_html escapes all text

            st.subheader("Comparison")
            before, after = text_stats(text), text_stats(result)
            st.table({"Original": {k: str(v) for k, v in before.items()},  # str: avoid "13.0000"
                      "Rewritten": {k: str(v) for k, v in after.items()}})
            c1, c2 = st.columns(2)
            c1.metric("Words kept (similarity)", f"{similarity(text, result):.0%}")
            c2.metric("All numbers kept?", "Yes" if numbers_kept(text, result) else "No — check!")
