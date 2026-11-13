"""Offline checks for the non-LLM logic. Run with: python test_rewriter.py"""
from rewriter import PROMPT_V2, STYLES, diff_html, numbers_kept, rewrite, similarity, text_stats

# diff marks removed/added words and escapes HTML
assert diff_html("i has a pen", "I have a pen") == "<del>i has</del> <ins>I have</ins> a pen"
assert "&lt;b&gt;" in diff_html("<b>", "x")
assert diff_html("one\ntwo", "one\ntwo") == "one<br>two"          # line breaks survive
assert diff_html("a\n\nb", "a\n\nb").count("<br>") == 2           # paragraphs survive
assert diff_html("one two", "one\ntwo") == "one <ins><br></ins> two"  # added line break is shown

# similarity: identical = 1, nothing shared = 0
assert similarity("a b c", "a b c") == 1.0
assert similarity("a b", "c d") == 0.0

# numbers check catches a changed or dropped number
assert numbers_kept("Room 204 at 3:30", "At 3:30 in room 204")
assert not numbers_kept("Budget 25000", "Budget 2500")
assert numbers_kept("Budget 25000", "Budget 25,000")

assert text_stats("The library is closed today. Students can return books tomorrow.")["Sentences"] == 2

# prompt fills in style rules and the user text
msgs = PROMPT_V2.format_messages(text="hello", style="Formal", style_rules=STYLES["Formal"])
assert "formal" in msgs[0].content and "hello" in msgs[1].content

# input validation runs before any API call
for bad in ["   ", "x" * 5001]:
    try:
        rewrite(bad, "Formal")
        raise AssertionError("should have failed")
    except ValueError:
        pass

print("All checks passed.")
