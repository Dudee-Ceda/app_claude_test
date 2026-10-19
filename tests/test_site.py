"""docs/index.html (the public static site) must be rebuilt whenever web/index.html changes."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_docs_site_is_up_to_date():
    spec = importlib.util.spec_from_file_location("build_web", ROOT / "scripts" / "build_web.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    built = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
    assert built == mod.build(), "run: python scripts/build_web.py"
    assert built.startswith("<!doctype html>") and built.rstrip().endswith("</html>")
