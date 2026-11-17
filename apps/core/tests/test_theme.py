"""The colour ramps exist twice: in tailwind.config.js, which the production image
compiles, and inline in templates/_assets.html, which the DEBUG CDN build uses
because it cannot read the config file. They must agree, or the app looks like one
palette locally and another on the server.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _config_ramp(name):
    cfg = (ROOT / "tailwind.config.js").read_text(encoding="utf-8")
    block = re.search(rf"const {name}\s*=\s*{{(.*?)\n}};", cfg, re.S).group(1)
    return {k: v.upper() for k, v in re.findall(r"(\d+):\s*\"(#[0-9A-Fa-f]{6})\"", block)}


def _assets_ramp(name):
    assets = (ROOT / "templates" / "_assets.html").read_text(encoding="utf-8")
    raw = re.search(rf"{name}: (\{{.*?\}})", assets).group(1)
    return {k: v.upper() for k, v in json.loads(raw).items()}


def test_teal_ramp_matches():
    assert _assets_ramp("teal") == _config_ramp("matcha")


def test_slate_ramp_matches():
    assert _assets_ramp("slate") == _config_ramp("warmGrey")


def test_tokens_use_the_palette():
    """The five palette colours must all still appear in the :root block."""
    css = (ROOT / "templates" / "_components.css").read_text(encoding="utf-8")
    root = css[css.index(":root {"): css.index("html {")]
    for colour in ("#F4F1E8", "#C9D6A3", "#6B8F47", "#E8B87A", "#2F3B24"):
        assert colour in root, f"{colour} is no longer in the token block"
