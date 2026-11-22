"""Rebuild everything:  uv run python build.py

  hook/   reusable hook: profile (DXF/SVG), STEP bodies, fit-test STL + 3MF
  ptfe/   PTFE parts: STLs + print plate 3MF
  docs/   README preview images
"""
import subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY = sys.executable


def run(*args):
    print("+", " ".join(map(str, args)), flush=True)
    subprocess.run([PY, *map(str, args)], cwd=ROOT, check=True)


run("-m", "slathook")
run("ptfe/ptfe_mount.py")
p = "ptfe/stl/"
run("tools/make_3mf.py", "ptfe/slatwall_ptfe_plate.3mf", "tools/prusa/cfg.ini",
    p + "sleeve_2.stl:4", p + "sleeve_3.stl:2", p + "sleeve_4.stl:2", p + "sleeve_5.stl:4",
    p + "swivel_base.stl:4", p + "swivel_guide_5.stl:4")
run("tools/make_3mf.py", "hook/hook_fit_test.3mf", "tools/prusa/cfg_fit.ini", "hook/fit_test.stl:1")
run("tools/render.py", "docs/img", "hook/fit_test.stl@mounted", p + "swivel_base.stl@mounted",
    p + "swivel_guide_5.stl", *(f"{p}sleeve_{n}.stl" for n in (2, 3, 4, 5)))
