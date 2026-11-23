"""Assemble the static GitHub Pages site into _site/.

site/ holds the pages; the Python geometry the browser runs (Pyodide) is copied in from the repo so
the web generators and the CLI share one implementation. Capacity tables (site/*/table.json) are
precomputed offline (e.g. bracket/shelf_table.py) and committed.

    uv run python tools/build_site.py && python -m http.server -d _site 8000
"""
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "_site"
PY = {                                    # browser path under _site/py/ -> repo file
    "slathook/__init__.py": "slathook/__init__.py",
    "slathook/profile.py": "slathook/profile.py",
    "shelf_geom.py": "bracket/shelf_geom.py",
}

if OUT.exists():
    shutil.rmtree(OUT)
shutil.copytree(ROOT / "site", OUT, ignore=shutil.ignore_patterns("__pycache__"))
for dst, src in PY.items():
    (OUT / "py" / dst).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / src, OUT / "py" / dst)
shutil.copy2(ROOT / "tools/prusa/cfg_extruded.ini", OUT / "common/printer.ini")
(OUT / ".nojekyll").write_text("")
print("built", OUT)
