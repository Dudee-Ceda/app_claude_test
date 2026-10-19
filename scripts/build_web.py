"""Build the standalone public site docs/index.html from web/index.html.

web/index.html is the page body (as published to Claude artifacts). This script wraps it into a
complete HTML document that any static host can serve: GitHub Pages (folder /docs), Netlify,
Cloudflare Pages, or a plain web server.

    python scripts/build_web.py
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "web" / "index.html"
OUT = ROOT / "docs" / "index.html"

DESCRIPTION = (
    "RC Slab Design — โปรแกรมออกแบบพื้นคอนกรีตเสริมเหล็ก ทางเดียวและสองทาง (ACI / ว.ส.ท., Method 2) "
    "ตรวจการแอ่นตัว ถอดปริมาณวัสดุ และตารางเหล็กพื้นสำหรับทำแบบ"
)
FAVICON = (
    "data:image/svg+xml,"
    "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E"
    "%3Crect width='32' height='32' rx='6' fill='%232b5c8a'/%3E"
    "%3Cpath d='M6 10h20M6 16h20M6 22h20M10 6v20M16 6v20M22 6v20' stroke='%23fbfbf8' stroke-width='2'/%3E"
    "%3C/svg%3E"
)
BASE_STYLE = "<style>html{color-scheme:light}body{margin:0}img{max-width:100%}</style>"


def build() -> str:
    src = SRC.read_text(encoding="utf-8")
    split = src.index('<div class="wrap">')
    head, body = src[:split], src[split:]
    head = head.replace('<meta name="claude:viewport-fit-sides" content="cover">\n', "")
    return (
        "<!doctype html>\n"
        '<html lang="th">\n<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
        f'<meta name="description" content="{DESCRIPTION}">\n'
        '<meta property="og:title" content="RC Slab Design">\n'
        f'<meta property="og:description" content="{DESCRIPTION}">\n'
        f'<link rel="icon" href="{FAVICON}">\n'
        f"{BASE_STYLE}\n"
        f"{head.strip()}\n"
        "</head>\n<body>\n"
        f"{body.strip()}\n"
        "</body>\n</html>\n"
    )


if __name__ == "__main__":
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(build(), encoding="utf-8")
    (OUT.parent / ".nojekyll").write_text("")
    print(f"wrote {OUT.relative_to(ROOT)}")
