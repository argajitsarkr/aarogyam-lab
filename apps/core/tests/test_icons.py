"""The Material Symbols font is subset to the icons we use (3 MB -> ~15 KB), so the
list in templates/_assets.html must stay in step with the {% icon %} tags. An icon
missing from the subset silently renders as its own name in plain text."""
import re
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parents[3] / "templates"


def used_icon_names():
    names = set()
    for p in TEMPLATES.rglob("*.html"):
        names |= set(re.findall(r'\{%\s*icon\s+"([a-z0-9_]+)"', p.read_text(encoding="utf-8")))
    return names


def subset_icon_names():
    assets = (TEMPLATES / "_assets.html").read_text(encoding="utf-8")
    m = re.search(r"icon_names=([a-z0-9_,]+)", assets)
    assert m, "no icon_names= in the Material Symbols link"
    return set(m.group(1).split(","))


def test_every_icon_used_is_in_the_subset():
    missing = sorted(used_icon_names() - subset_icon_names())
    assert not missing, f"add to icon_names= in templates/_assets.html: {','.join(missing)}"


def test_subset_has_nothing_unused():
    extra = sorted(subset_icon_names() - used_icon_names())
    assert not extra, f"no longer used, drop from icon_names=: {','.join(extra)}"


def test_subset_list_is_sorted():
    assets = (TEMPLATES / "_assets.html").read_text(encoding="utf-8")
    listed = re.search(r"icon_names=([a-z0-9_,]+)", assets).group(1).split(",")
    assert listed == sorted(listed), "keep icon_names= alphabetical"
