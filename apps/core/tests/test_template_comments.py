"""A `{# ... #}` comment in a Django template must fit on ONE line. Spread over
several lines it is not a comment at all: the first line is dropped and the rest
is rendered as text and parsed as tags, which has leaked a comment onto two pages
already. Multi-line notes use {% comment %} ... {% endcomment %}.
"""
import re
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parents[3] / "templates"


def test_no_multiline_hash_comments():
    offenders = []
    for path in sorted(TEMPLATES.rglob("*.html")):
        text = path.read_text(encoding="utf-8")
        for m in re.finditer(r"\{#", text):
            end_of_line = text.find("\n", m.start())
            line = text[m.start(): end_of_line if end_of_line != -1 else len(text)]
            if "#}" not in line:
                offenders.append(f"{path.relative_to(TEMPLATES)}:{text[:m.start()].count(chr(10)) + 1}")
    assert not offenders, "use {% comment %} for multi-line notes: " + ", ".join(offenders)
