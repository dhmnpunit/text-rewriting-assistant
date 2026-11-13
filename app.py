"""ClearDraft, the Text Rewriting & Grammar Assistant. Run with: streamlit run app.py

One shared editor: style row on top, Original on the left, Rewrite on the right, each with a bottom bar.
Colours and the Inter font come from .streamlit/config.toml.
"""
import difflib
import hashlib
import html
import json
import os
import time

import streamlit as st

from rewriter import (MAX_INPUT_CHARS, MODELS, PROMPTS, STYLES, diff_html, find_numbers, numbers_kept, rewrite,
                      similarity, text_stats)

st.set_page_config(page_title="ClearDraft · Text Rewriting & Grammar Assistant", page_icon="✍️", layout="wide")

GREEN, GREEN_HOVER, BORDER, TEXT, MUTED = "#166A48", "#0F563A", "#D8E1DB", "#202522", "#5F6862"
PALE = "#EAF3EC"  # pale green for alternating lower-page bands
PANE_HEIGHT = 270       # text box and rewrite area share this height; long text scrolls inside each pane
SHORT_TEXT_WORDS = 30   # below this, readability formulas are not meaningful
EASE, GRADE = "Reading ease (0-100, higher = easier)", "School grade level"

# Demo inputs for "Try an example": each click loads the next one (ids from samples.json).
_samples = {s["id"]: s["text"] for s in json.load(open("samples.json", encoding="utf-8"))}
EXAMPLES = [_samples[i] for i in (2, 1, 5, 3, 8, 7)]

st.markdown(f"""<style>
[data-testid="stHeader"]{{display:none}}
[data-testid="stMainBlockContainer"]{{max-width:1168px;padding:0 24px 0}}  /* 1,120px content + 24px gutters */
@media (max-width:640px){{[data-testid="stMainBlockContainer"]{{padding:0 16px 0}}}}

/* Lower page: full-width bands (the background bleeds to the screen edges, the content keeps the editor's width). */
.st-key-lower{{gap:0;margin-top:40px}}
.st-key-sec_how,.st-key-sec_diff,.st-key-sec_faq,.st-key-sec_end{{padding:56px 0}}
@media (max-width:640px){{.st-key-sec_how,.st-key-sec_diff,.st-key-sec_faq,.st-key-sec_end{{padding:32px 0}}}}
/* A second shadow, shifted up 1px, draws the thin divider line across the full screen width too. */
.st-key-sec_how,.st-key-sec_faq{{background:{PALE};box-shadow:0 0 0 100vmax {PALE},0 -1px 0 100vmax {BORDER};
  clip-path:inset(-1px -100vmax 0)}}
.st-key-sec_diff,.st-key-sec_end{{background:#FFFFFF;box-shadow:0 0 0 100vmax #FFFFFF,0 -1px 0 100vmax {BORDER};
  clip-path:inset(-1px -100vmax 0)}}
.sec-h{{font-size:1.75rem;font-weight:700;letter-spacing:-.01em;color:{TEXT};margin:0 0 8px;line-height:1.25}}
.sec-p{{color:{MUTED};margin:0;font-size:1rem;line-height:1.6}}
.center{{text-align:center}}
.st-key-sec_how span[role="img"]{{font-size:30px !important;color:{GREEN};background:{PALE};border-radius:10px;
  padding:7px;line-height:1}}
.step-t{{font-weight:600;font-size:1.05rem;color:{TEXT};margin:10px 0 4px}}
.step-p{{color:{MUTED};margin:0;line-height:1.55}}
.st-key-how_1,.st-key-how_2,.st-key-how_3{{background:#FFFFFF;border:1px solid {BORDER};border-radius:12px;padding:22px}}
.style-row{{margin-top:18px;line-height:1.6;color:{TEXT}}}
.style-row b{{color:{GREEN}}}
/* Before | After preview: the main visual of the lower page. */
.ba{{border:1px solid {BORDER};border-radius:12px;overflow:hidden;background:#FFFFFF;display:grid;grid-template-columns:1fr 1fr}}
.ba > div{{padding:18px 20px}}
.ba > div + div{{border-left:1px solid {BORDER}}}
.ba .tag{{font-size:.75rem;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:{MUTED};margin-bottom:8px}}
.ba .txt{{line-height:1.7;color:{TEXT}}}
.ba del{{background:rgba(190,48,48,.10);color:#9B2C2C;text-decoration:line-through;border-radius:3px;padding:0 2px}}
.ba ins{{background:rgba(22,106,72,.12);color:inherit;text-decoration:none;border-bottom:2px solid {GREEN};padding:0 2px}}
.ba-cap{{font-size:.82rem;color:{MUTED};margin-top:8px}}
@media (max-width:640px){{.ba{{grid-template-columns:1fr}} .ba > div + div{{border-left:none;border-top:1px solid {BORDER}}}}}
.st-key-try_sample button,.st-key-back_editor button{{border:1px solid {GREEN};color:{GREEN};background:#FFFFFF;min-height:40px;padding:0 18px}}
.st-key-try_sample button:hover,.st-key-back_editor button:hover{{background:{PALE};color:{GREEN_HOVER};border-color:{GREEN_HOVER}}}
.st-key-sec_faq [data-testid="stExpander"] details{{background:#FFFFFF;border-color:{BORDER}}}
.st-key-sec_faq [data-testid="stExpander"] summary{{padding-top:12px;padding-bottom:12px;font-weight:500}}
.st-key-end_band{{background:{PALE};border:1px solid {BORDER};border-radius:12px;padding:32px 24px}}
.topbar{{display:flex;align-items:center;gap:10px;padding:12px 0;margin-bottom:8px;border-bottom:1px solid {BORDER}}}
.topbar .mark{{width:32px;height:32px;border-radius:8px;background:{GREEN};color:#fff;display:flex;
  align-items:center;justify-content:center;font-weight:700;font-size:16px}}
.topbar .name{{font-weight:700;font-size:1.05rem;line-height:1.15;color:{TEXT}}}
.topbar .sub{{font-size:.8rem;color:{MUTED};line-height:1.2}}

/* One shared editor: a single crisp 1px border, 12px corners, flat white. */
.st-key-editor{{background:#FFFFFF;border:1px solid {BORDER};border-radius:12px;gap:0;overflow:hidden}}
.st-key-modes{{padding:10px 20px;border-bottom:1px solid {BORDER}}}
.st-key-pane_left,.st-key-pane_right{{padding:14px 20px 0}}
.st-key-pane_right{{border-left:1px solid {BORDER}}}  /* centre divider, same colour as the border */
@media (max-width:640px){{.st-key-pane_right{{border-left:none;border-top:1px solid {BORDER}}}}}
.st-key-head_left,.st-key-head_right{{min-height:40px}}
/* Bottom bars run edge to edge across their pane, with the same border colour. */
.st-key-bar_left,.st-key-bar_right{{margin:0 -20px;width:calc(100% + 40px) !important;max-width:none;
  padding:12px 20px;border-top:1px solid {BORDER};min-height:65px}}
.pane-label{{font-weight:600;font-size:.95rem;color:{TEXT};padding:6px 0}}

/* The text box blends into the pane; a green ring shows keyboard focus. */
.st-key-pane_left [data-testid="stTextAreaRootElement"]{{border-color:transparent !important;background:#FFFFFF;
  border-radius:8px}}
.st-key-pane_left [data-testid="stTextAreaRootElement"]:focus-within{{border-color:transparent !important;
  box-shadow:none;outline:2px solid {GREEN};outline-offset:-2px}}
.st-key-pane_left textarea{{font-size:1.02rem;line-height:1.7;background:#FFFFFF;padding-left:10px;padding-right:10px}}

/* Rewrite: the only solid green button, with hover, focus and busy states. Copy rewrite stays outlined. */
.st-key-go button{{min-height:40px;padding:0 20px;font-weight:600}}
.st-key-go button:hover:not(:disabled){{background:{GREEN_HOVER};border-color:{GREEN_HOVER};color:#fff}}
.st-key-go button:disabled{{background:#4C8C70 !important;border-color:#4C8C70 !important;color:#fff !important;cursor:progress}}
.st-key-copy_disabled button{{min-height:40px}}
[class*="st-key-head_"] button[kind="tertiary"]:hover{{color:{GREEN}}}
button:focus-visible,[role="radio"]:focus-visible,[role="switch"]:focus-visible,summary:focus-visible{{
  outline:2px solid {GREEN} !important;outline-offset:2px}}

.placeholder{{height:{PANE_HEIGHT - 16}px;display:flex;align-items:center;justify-content:center;color:#8C948F;text-align:center}}
.doc{{white-space:pre-wrap;line-height:1.7;font-size:1.02rem;color:{TEXT};padding:8px 0}}
.doc del{{background:rgba(190,48,48,.10);color:#9B2C2C;text-decoration:line-through;border-radius:3px;padding:0 2px}}
.doc ins{{background:rgba(22,106,72,.12);color:inherit;text-decoration:none;border-bottom:2px solid {GREEN};
  border-radius:3px 3px 0 0;padding:0 2px}}
</style>""", unsafe_allow_html=True)

# Shared look for the two small HTML buttons below (they render outside Streamlit's widgets).
BUTTON_CSS = f"""<style>
.cd-btn{{font:inherit;font-size:.88rem;font-weight:500;color:{TEXT};background:#fff;border:1px solid {BORDER};
  border-radius:999px;min-height:40px;padding:0 16px;cursor:pointer;white-space:nowrap;display:inline-flex;
  align-items:center;gap:6px}}
.cd-btn:hover{{background:#F1F6F3;border-color:#BFCDC4}}
.cd-btn:focus-visible{{outline:2px solid {GREEN};outline-offset:2px}}
.cd-btn.done{{color:{GREEN};border-color:{GREEN}}}
.cd-link{{border:none;background:none;min-height:32px;padding:0 4px}}
.cd-link:hover{{background:none;color:{GREEN}}}
</style>"""


def doc(inner):
    """Already-escaped HTML in the document style."""
    return f'<div class="doc">{inner}</div>'


def copy_button(text, uid):
    """'Copy rewrite': copies the clean text and shows 'Copied' for a moment."""
    return f"""{BUTTON_CSS}
<button class="cd-btn" id="copy-{uid}">Copy rewrite</button>
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
    btn.textContent = "Copied ✓"; btn.classList.add("done");
    setTimeout(() => {{ btn.textContent = "Copy rewrite"; btn.classList.remove("done"); }}, 1500);
  }});
}})();
</script>"""


# 'Paste text': reads the clipboard into the Original box. If the browser blocks clipboard
# reading, it focuses the box and asks for Ctrl/⌘+V instead.
PASTE_BUTTON = f"""{BUTTON_CSS}
<button class="cd-btn cd-link" id="cd-paste"><span>Paste text</span></button>
<script>
(() => {{
  const root = (document.currentScript && document.currentScript.getRootNode()) || document;
  const btn = root.querySelector("#cd-paste");
  if (!btn || btn.dataset.ready) return;
  btn.dataset.ready = "1";
  btn.addEventListener("click", async () => {{
    const box = document.querySelector(".st-key-pane_left textarea");
    if (!box) return;
    try {{
      const clip = await navigator.clipboard.readText();
      box.focus();
      if (!clip) return;
      // Set the value the way React expects, then blur so Streamlit saves it.
      Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value").set.call(box, clip);
      box.dispatchEvent(new Event("input", {{ bubbles: true }}));
      box.blur();
    }} catch (e) {{
      box.focus();
      btn.querySelector("span").textContent = "Press Ctrl/⌘+V";
      setTimeout(() => {{ btn.querySelector("span").textContent = "Paste text"; }}, 2500);
    }}
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


def start_rewrite():
    # Runs before the rerun, so the button can already show "Rewriting…" while the model works.
    st.session_state.pending = True


def row(key, **kw):
    """A horizontal row: items spread to both ends, vertically centred."""
    return st.container(key=key, horizontal=True, vertical_alignment="center", horizontal_alignment="distribute", **kw)


# --- Header ---
st.html("""<div class="topbar"><div class="mark">✎</div>
<div><div class="name">ClearDraft</div><div class="sub">Text Rewriting &amp; Grammar Assistant</div></div></div>""")

# The editor is drawn first on the page but filled in last, because it needs the values from
# "Advanced settings", which sit below it. Streamlit containers can be filled in any order.
editor = st.container(key="editor")
stats_area = st.container()

with st.expander("Advanced settings", icon=":material/tune:"):
    c1, c2 = st.columns(2, gap="large")
    model = c1.selectbox("Model (Groq)", MODELS)
    prompt = c1.radio("Prompt version", list(PROMPTS), horizontal=True,
                      help="v1 = basic prompt, v2 = improved prompt")
    temperature = c2.slider("Temperature", 0.0, 1.0, 0.3, 0.1,
                            help="Low = safe, consistent edits. High = more creative, more varied.")
    max_tokens = c2.slider("Max tokens", 256, 4096, 2048, 256, help="Upper limit on the output length.")

# --- Lower page: How it works, See the difference, FAQ, Back to editor ---
# A real result from results.csv: sample #1, Formal style, prompt v2.
PREVIEW_STYLE = "Formal"
PREVIEW_BEFORE = _samples[1]
PREVIEW_AFTER = ("I submitted the assignment yesterday, but it was not uploaded properly. "
                 "Could you please check it and advise me on what I should do now?")


def before_after(a, b):
    """Word diff split in two: removed words marked in the Before text, added words in the After text."""
    a_words, b_words = a.split(), b.split()
    before, after = [], []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a_words, b_words).get_opcodes():
        old, new = html.escape(" ".join(a_words[i1:i2])), html.escape(" ".join(b_words[j1:j2]))
        before.append(old if op == "equal" or not old else f"<del>{old}</del>")
        after.append(new if op == "equal" or not new else f"<ins>{new}</ins>")
    return " ".join(x for x in before if x), " ".join(x for x in after if x)


def go_to_editor():
    st.session_state.scroll_to_editor = True


def try_sample():
    st.session_state.draft = PREVIEW_BEFORE
    st.session_state.styles = [PREVIEW_STYLE]  # so the user's Rewrite matches the preview
    go_to_editor()


with st.container(key="lower"):
    with st.container(key="sec_how"):
        st.html('<div class="center"><h2 class="sec-h">How ClearDraft works</h2>'
                '<p class="sec-p">Three steps from a rough draft to clear writing.</p></div>')
        steps = [(":material/content_paste:", "Paste your text", "Type, paste or load an example into Original."),
                 (":material/tune:", "Choose a style", "Pick Grammar Fix, Formal, Simple or Concise, or several."),
                 (":material/compare_arrows:", "Compare and copy", "See every change highlighted, then copy the rewrite.")]
        for i, (col, (icon, title, line)) in enumerate(zip(st.columns(3, gap="medium"), steps), start=1):
            with col, st.container(key=f"how_{i}"):
                st.markdown(icon)
                st.html(f'<div class="step-t">{title}</div><p class="step-p">{line}</p>')

    with st.container(key="sec_diff"):
        text_col, preview_col = st.columns([1, 1.35], gap="large", vertical_alignment="center")
        with text_col:
            st.html(f"""<h2 class="sec-h">See the difference</h2>
<p class="sec-p">Each style follows its own rules, so you get the version you need.</p>
<div class="style-row"><b>Formal</b> turns casual writing into a polite, professional message.</div>
<div class="style-row"><b>Concise</b> cuts filler and repetition but keeps every key point.</div>""")
            st.button("Try this example", key="try_sample", on_click=try_sample, icon=":material/north_west:")
        with preview_col:
            b_html, a_html = before_after(PREVIEW_BEFORE, PREVIEW_AFTER)
            st.html(f"""<div class="ba"><div><div class="tag">Before</div><div class="txt">{b_html}</div></div>
<div><div class="tag">After · {PREVIEW_STYLE}</div><div class="txt">{a_html}</div></div></div>
<div class="ba-cap">A real result from our tests (sample #1, Formal style, prompt v2).</div>""")

    with st.container(key="sec_faq"):
        st.html('<div class="center"><h2 class="sec-h" style="margin-bottom:20px">Questions</h2></div>')
        with st.expander("Which style should I choose?"):
            st.write("**Grammar Fix** only corrects mistakes. **Formal** suits emails to teachers or managers. "
                     "**Simple** makes text easy to read. **Concise** makes it shorter. Not sure? Pick several "
                     "and compare the tabs.")
        with st.expander("What does Show changes highlight?"):
            st.write("It compares the rewrite with your original word by word: removed words are red and "
                     "crossed out, added words are green and underlined.")
        with st.expander("Can a rewrite change my meaning?"):
            st.write("Sometimes, yes. The prompt tells the model to keep your meaning, names and numbers, and "
                     "Rewrite stats shows how many words were kept and whether every number survived. Always "
                     "read the rewrite before you use it.")

    with st.container(key="sec_end"), st.container(key="end_band", horizontal=True, vertical_alignment="center",
                                                   horizontal_alignment="distribute"):
        st.html('<div><h2 class="sec-h" style="font-size:1.35rem;margin:0">Ready to make your writing clearer?</h2>'
                '<p class="sec-p">Your draft is still in the editor.</p></div>', width="content")
        st.button("Back to editor", key="back_editor", on_click=go_to_editor, icon=":material/arrow_upward:")

pending = st.session_state.get("pending", False)
just_generated = False

with editor:
    # Top row of the editor: the four rewrite styles.
    with st.container(key="modes"):
        picked = st.pills("Rewrite styles", list(STYLES), selection_mode="multi", key="styles",
                          default=["Grammar Fix", "Formal"], label_visibility="collapsed")
    styles = [s for s in STYLES if s in (picked or [])]  # always in picker order, whatever the click order

    left, right = st.columns(2, gap=None)

    with left, st.container(key="pane_left"):
        text = st.session_state.get("draft", "")
        with row("head_left"):
            st.html('<div class="pane-label">Original</div>', width="content")
            with st.container(horizontal=True, width="content", vertical_alignment="center", gap="small"):
                if not text.strip():
                    st.html(PASTE_BUTTON, width="content", unsafe_allow_javascript=True)
                st.button("Try an example", on_click=load_example, type="tertiary", icon=":material/lightbulb:")
        text = st.text_area("Original", key="draft", height=PANE_HEIGHT, label_visibility="collapsed",
                            placeholder="Paste or type the text you want to improve...")
        with row("bar_left"):
            words = len(text.split())
            st.caption(f"{words} word{'' if words == 1 else 's'} · {len(text)} / {MAX_INPUT_CHARS} characters")
            st.button("Rewriting…" if pending else "Rewrite", type="primary", key="go", on_click=start_rewrite,
                      icon="spinner" if pending else ":material/auto_fix_high:", disabled=pending)

    with right, st.container(key="pane_right"):
        # Streamlit reruns this whole script on every click, so the last result is kept in session_state.
        if pending:
            st.session_state.pending = False
            just_generated = True
            if not text.strip():
                st.session_state.last = {"error": "Please enter some text first, or click **Try an example**."}
            elif not styles:
                st.session_state.last = {"error": "Pick at least one rewrite style at the top of the editor."}
            else:
                results = {}
                for style in styles:
                    start = time.time()
                    try:
                        with st.spinner(f"Rewriting ({style})…"):
                            results[style] = {"text": rewrite(text, style, prompt, model, temperature, max_tokens)}
                    except Exception as e:  # too long, bad key, rate limit, network
                        results[style] = {"error": friendly_error(e)}
                    results[style]["seconds"] = round(time.time() - start, 1)
                st.session_state.last = {"text": text, "results": results, "model": model, "prompt": prompt,
                                         "temperature": temperature, "max_tokens": max_tokens}
                st.session_state.active = styles[0]

        last = st.session_state.get("last")
        results = (last or {}).get("results", {})

        # Header: "Rewrite" plus one tab per generated style, aligned with the "Original" header.
        with row("head_right"):
            st.html('<div class="pane-label">Rewrite</div>', width="content")
            if len(results) > 1:
                if st.session_state.get("active") not in results:
                    st.session_state.active = next(iter(results))
                st.segmented_control("Result tabs", list(results), key="active", label_visibility="collapsed",
                                     required=True)
        active = st.session_state.get("active") if len(results) > 1 else next(iter(results), None)
        res = results.get(active, {})

        with st.container(height=PANE_HEIGHT, border=False):
            if not last:
                st.html('<div class="placeholder">Your rewrite will appear here.</div>')
            elif "error" in last:
                st.error(last["error"], icon=":material/error:")
                st.caption("Your draft is kept.")
            elif "error" in res:
                st.error(f"{active}: {res['error']}", icon=":material/error:")
                st.caption("Your draft is kept. Try again.")
            else:
                if last["text"] != text:
                    st.caption(":material/info: This is the rewrite of your previous text. "
                               "Click **Rewrite** to update it.")
                show = st.session_state.get(f"changes_{active}", False)
                # diff_html and html.escape both escape the text, so nothing in it can inject HTML
                st.html(doc(diff_html(last["text"], res["text"]) if show else html.escape(res["text"])))

        # Bottom bar: Show changes on the left; word count and Copy rewrite on the right.
        with row("bar_right"):
            ready = "text" in res
            st.toggle("Show changes", key=f"changes_{active}" if ready else "changes_none", disabled=not ready,
                      help="Red = removed, green = added")
            with st.container(horizontal=True, width="content", vertical_alignment="center", gap="small"):
                if ready:
                    n = len(res["text"].split())
                    st.caption(f"{n} word{'' if n == 1 else 's'}")
                    uid = hashlib.md5(f"{active}{res['text']}".encode()).hexdigest()[:10]
                    st.html(copy_button(res["text"], uid), width="content", unsafe_allow_javascript=True)
                else:
                    st.button("Copy rewrite", disabled=True, key="copy_disabled")

    if not os.getenv("GROQ_API_KEY"):
        st.error("GROQ_API_KEY not found. Copy .env.example to .env and paste your key from console.groq.com.")

# --- Rewrite stats: metrics, full table, generation details (collapsed) ---
last = st.session_state.get("last")
done = {s: r for s, r in (last or {}).get("results", {}).items() if "text" in r}
if done:
    with stats_area, st.expander("Rewrite stats", icon=":material/analytics:"):
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

# "Try this example" / "Back to editor": scroll up to the editor and put the cursor in Original.
if st.session_state.pop("scroll_to_editor", False):
    st.html(f"""<script>/* {time.time()} */
setTimeout(() => {{
  const ed = document.querySelector(".st-key-editor");
  if (ed) ed.scrollIntoView({{behavior: "smooth", block: "start"}});
  const box = document.querySelector(".st-key-pane_left textarea");
  if (box) box.focus({{preventScroll: true}});
}}, 150);
</script>""", unsafe_allow_javascript=True)

# After generating, rerun once so the button switches back from "Rewriting…" to "Rewrite".
if just_generated:
    st.rerun()
