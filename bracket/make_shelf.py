"""One-piece shelf: three identical twin-wall ladders (deck, diagonal, wall spine) + three joints,
parametric in width (along the wall = print height) and depth.

    uv run python make_shelf.py WIDTH_MM DEPTH_MM [name]      e.g. 152.4 101.6 shelf_6x4
"""
import re, subprocess, sys, warnings
warnings.filterwarnings("ignore")
import os
os.environ.setdefault("FEA_H", "0.25")
from extruded import score, P, tri_ladder
from make_catalog import to_part
from build123d import export_stl

import argparse
ap = argparse.ArgumentParser()
ap.add_argument("width", type=float); ap.add_argument("depth", type=float); ap.add_argument("name", nargs="?")
ap.add_argument("--perims", type=int, default=2, help="perimeters per ladder wall and lacing")
ap.add_argument("--smooth", type=float, default=0.4, help="inside fillet radius (mm); bigger = stiffer joints")
ap.add_argument("--pitch", type=float, default=10.0, help="lacing pitch (mm)")
ap.add_argument("--joint-r", type=float, default=2.0, help="joint corner radius (mm)")
ap.add_argument("--S", type=float, default=6.0, help="twin-wall spacing (mm)")
a = ap.parse_args()
width, depth = a.width, a.depth
name = a.name or f"shelf_{width:.0f}x{depth:.0f}"
kw = dict(S=a.S, wall=P(a.perims), lace=P(a.perims), lace_pitch=a.pitch, smooth=a.smooth, joint_r=a.joint_r, depth=depth)
r = score(("tri_ladder", dict(kw, width=width)))
print(f"{name}: {width:.0f} wide x {depth:.0f} deep -> safe {r['kg']:.1f} kg on the shelf "
      f"{({k: round(v, 1) for k, v in r['lim'].items()})}")
part = to_part(tri_ladder(**kw), width, width)
bb = part.bounding_box().size
print(f"print footprint {bb.X:.0f} x {bb.Y:.0f} mm, {bb.Z:.0f} mm tall")
stl, tmf = f"out/print/{name}.stl", f"out/print/{name}.3mf"
export_stl(part, stl)
subprocess.run(["uv", "run", "python", "../tools/make_3mf.py", tmf, "../tools/prusa/cfg_extruded.ini", f"{stl}:1"], check=True, capture_output=True)
PS = r"C:\Program Files\Prusa3D\PrusaSlicer\prusa-slicer-console.exe"
subprocess.run([PS, "--dont-arrange", "--binary-gcode=0", "--export-gcode", tmf, "-o", "out/print/tmp.gcode"], check=True, capture_output=True)
g = open("out/print/tmp.gcode").read()
print("sliced", re.search(r"filament used \[g\] = ([\d.]+)", g).group(1), "g,",
      re.search(r"estimated printing time \(normal mode\) = (.+)", g).group(1), "->", tmf)
