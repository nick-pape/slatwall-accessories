"""Shelf generator: one-piece twin-wall-ladder shelf for any width x depth.

Picks the lightest shape that safely carries a water column over the deck:
  * "L"     deck + short wall spine (no diagonal)                 -- shallow shelves
  * "T45"   deck + spine + diagonal whose foot presses on the wall face at 45 deg (spine in tension)
  * "T55"   same, steeper (55 deg), if the foot still lands above the next slot
  * "slot"  diagonal foot rests in the next slot down (height fixed, angle flattens with depth)
Each candidate is sized up from the thinnest printable ladder until it passes the FEA
(creep 10 MPa, strength / 2, buckling / 3), then the lightest passing one is written as a 3MF.

    uv run python shelf_gen.py WIDTH_MM DEPTH_MM [--water-cm 20] [--load KG] [--lip 1.5] [--open]
Width runs along the wall (= print height, <= 220); depth is the stick-out.
"""
import argparse, math, os, re, subprocess, sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union
from shapely import contains_xy

from shelf_geom import (TOP, RF, SIZES, LIP_T, LIP_X0, frame, candidates, lip_profile, side_lips)  # noqa: F401
from model import Bracket
from evaluate import evaluate

HERE = Path(__file__).parent
SAG_RATIO = 300.0      # elastic tip sag <= depth / 300 under the rated load (creep roughly doubles it over time)


def evaluate_geom(geom, depth, width, bottom, rest):
    h = float(os.environ.get("FEA_H", "0.4"))
    m = Bracket(depth=depth, z_bottom=min(bottom - 6, -20.0), h=h, t=width, rest=rest)
    r = evaluate(m, contains_xy(geom, m.grid.xc, m.grid.zc), P=100.0)
    lim = {k: v / 9.81 for k, v in r["limits_N"].items()}
    tip = max(r["cases"]["uniform"]["tip_mm"], 1e-6)                 # mm of tip sag per 100 N, even load
    lim["sag"] = (depth / SAG_RATIO) / tip * 100.0 / 9.81
    return min(lim.values()), r["mass"], lim


def generate(width, depth, load_kg, log=print):
    best = None
    for name, kw in candidates(depth):
        for perims, S in SIZES:
            geom, bottom = frame(depth, S=S, perims=perims, **kw)
            kg, mass, lim = evaluate_geom(geom, depth, width, bottom, kw.get("rest", False))
            if kg >= load_kg:
                log(f"  {name:5s} passes with {perims} perimeters, {S:.0f} mm ladders: {mass:6.1f} g (solid-eq), "
                    f"safe {kg:6.1f} kg, limited by {min(lim, key=lim.get)}")
                if best is None or mass < best[2]:
                    best = (name, dict(kw, S=S, perims=perims), mass, kg, geom)
                break
        else:
            log(f"  {name:5s} can't reach {load_kg:.1f} kg with the sizes tried")
    return best




def to_part_lip(geom, width, depth, lip=0.0):
    """Extrude the profile `width` tall (print orientation). lip > 0 adds a chamfered lip of that height
    along the front edge and both side edges of the deck (side lips stop LIP_X0 short of the wall)."""
    from make_catalog import to_part
    from build123d import Plane, Polygon as BPoly, extrude, BuildSketch, Location
    if lip <= 0:
        return to_part(geom, width, width)
    part = to_part(unary_union([geom, lip_profile(depth, lip)]), width, width)
    part = part.translate((0, 0, -part.bounding_box().min.Z))          # body spans z = 0..width
    for pts, x0 in side_lips(width, lip):
        with BuildSketch(Plane.YZ.offset(x0)) as sk:
            BPoly(*pts, align=None)
        part = part + extrude(sk.sketch, amount=depth - x0)
    return part


def write(width, depth, best, tag, lip=0.0):
    from build123d import export_stl
    name, kw, mass, kg, geom = best
    out = HERE / "out" / "print"
    stl, tmf = out / f"{tag}.stl", out / f"{tag}.3mf"
    export_stl(to_part_lip(geom, width, depth, lip), str(stl))
    subprocess.run([sys.executable, str(HERE.parent / "tools/make_3mf.py"), str(tmf),
                    str(HERE.parent / "tools/prusa/cfg_extruded.ini"), f"{stl}:1"], check=True, capture_output=True)
    PS = r"C:\Program Files\Prusa3D\PrusaSlicer\prusa-slicer-console.exe"
    if Path(PS).exists():
        (out / "tmp.gcode").unlink(missing_ok=True)                        # never report a stale slice
        subprocess.run([PS, "--dont-arrange", "--binary-gcode=0", "--export-gcode", str(tmf), "-o", str(out / "tmp.gcode")],
                       check=True, capture_output=True)
        g = (out / "tmp.gcode").read_text()
        grams = re.search(r"filament used \[g\] = ([\d.]+)", g).group(1)
        t = re.search(r"estimated printing time \(normal mode\) = (.+)", g).group(1)
        return tmf, f"{grams} g, {t}"
    return tmf, ""


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("width", type=float); ap.add_argument("depth", type=float)
    ap.add_argument("--water-cm", type=float, default=20.0, help="rated load as a water column over the deck")
    ap.add_argument("--load", type=float, help="rated load in kg (overrides --water-cm)")
    ap.add_argument("--name"); ap.add_argument("--open", action="store_true")
    ap.add_argument("--lip", type=float, default=0.0, help="chamfered lip height around the deck (mm), 0 = none")
    a = ap.parse_args()
    load = a.load if a.load else (a.width / 10) * (a.depth / 10) * a.water_cm / 1000.0
    print(f"{a.width:.0f} x {a.depth:.0f} mm shelf, rated {load:.1f} kg "
          f"({'fixed' if a.load else f'{a.water_cm:.0f} cm of water over the deck'})")
    best = generate(a.width, a.depth, load)
    if best is None:
        sys.exit("no candidate passed -- try a lower load or a smaller shelf")
    tag = a.name or f"shelf_{a.width:.0f}x{a.depth:.0f}"
    tmf, sliced = write(a.width, a.depth, best, tag, a.lip)
    print(f"-> {best[0]} ({best[1]['perims']} perimeters, {best[1]['S']:.0f} mm ladders), safe {best[3]:.1f} kg; "
          f"sliced {sliced}\n   {tmf}")
    if a.open:
        subprocess.Popen([r"C:\Program Files\Prusa3D\PrusaSlicer\prusa-slicer.exe", str(tmf)])
