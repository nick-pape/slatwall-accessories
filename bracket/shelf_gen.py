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

from extruded import ladder, P
from catalog import RF, TOP, HOOKP
from model import Bracket, REST_TAB
from slathook import SLOT_OPEN
from evaluate import evaluate

HERE = Path(__file__).parent
SAG_RATIO = 300.0      # elastic tip sag <= depth / 300 under the rated load (creep roughly doubles it over time)
SIZES = [(2, 6.0), (2, 8.0), (3, 6.0), (3, 8.0), (3, 10.0), (4, 10.0)]   # (perimeters, ladder spacing), light -> heavy


def _band(p, q, half, ext):
    u = (q - p) / np.linalg.norm(q - p)
    return LineString([p - u * ext, q + u * ext]).buffer(half, cap_style=2)


def _line_x(p, q, z):            # x where line p-q crosses height z
    return p[0] + (q[0] - p[0]) * (z - p[1]) / (q[1] - p[1])


def frame(depth, foot_z=None, rest=False, spine_len=None, S=6.0, perims=2, pitch=10.0, smooth=0.4, nose_r=3.0,
          inner_r=None):
    """Twin-wall ladders: deck always; spine down the wall; diagonal from the foot to the nose unless
    it's an L. Joints are solid ONLY where two ladders overlap; ladder ends are capped."""
    w = P(perims)
    half = S / 2 + w / 2
    A = np.array([half, TOP - half]); B = np.array([depth - half, TOP - half])
    if rest:
        C = np.array([half, RF + half])
    elif spine_len is not None:
        C = np.array([half, TOP - spine_len + half])
    else:
        C = np.array([half, foot_z])
    ext = 4 * S
    diag = spine_len is None
    lines = {"deck": (A, B), "spine": (C, A)} | ({"diag": (C, B)} if diag else {})
    # outer envelope: deck top, wall face, (diagonal underside), front x <= depth, bottom
    if diag:
        u = (B - C) / np.linalg.norm(B - C); n = np.array([u[1], -u[0]])          # outward (down/right) normal
        if n[1] > 0: n = -n
        c0, b0 = C + n * half, B + n * half
        x_top = _line_x(c0, b0, TOP)
        z_wall = c0[1] + (0 - c0[0]) * (b0[1] - c0[1]) / (b0[0] - c0[0])
        outer = Polygon([(0, TOP), (x_top, TOP), (0, z_wall)])
    else:
        outer = unary_union([box(0, TOP - 2 * half, depth, TOP), box(0, C[1] - half, 2 * half, TOP)])
    z_floor = (RF if rest else C[1] - half)
    outer = outer.intersection(box(0, z_floor, depth, TOP))
    bands = {k: _band(p, q, half, ext) for k, (p, q) in lines.items()}
    lad = unary_union(sum((ladder(p - (q - p) / np.linalg.norm(q - p) * ext, q + (q - p) / np.linalg.norm(q - p) * ext,
                                  S, w, w, pitch) for p, q in lines.values()), []))
    # joints = exactly where two ladders overlap; the OUTLINE is rounded at its corners (nose, foot),
    # except the top corner where the hook attaches, which stays square
    pairs = [("deck", "spine")] + ([("deck", "diag"), ("spine", "diag")] if diag else [])
    joints = [bands[i].intersection(bands[j]) for i, j in pairs]
    caps = [box(depth - w, TOP - 2 * half, depth, TOP)]
    if not diag:
        caps.append(box(0, C[1] - half, 2 * half, C[1] - half + w))
    env = outer.buffer(-nose_r, join_style=1).buffer(nose_r, join_style=1)
    keep_square = [box(0, TOP - 2 * half, 2 * half, TOP)]                     # under the hook
    if rest:
        keep_square.append(box(0, RF, 2 * half, RF + REST_TAB[1] + 1))       # behind the rest tab
    env = unary_union([env] + [k.intersection(outer) for k in keep_square])
    body = unary_union([lad, *joints, *caps]).intersection(env)
    # fillets in the inside corners of the open triangle (or the L's inside corner)
    R = 3.0 if inner_r is None else inner_r          # small inside-corner fillet (mm)
    if R > 0:
        if diag:
            hole = env.difference(unary_union(list(bands.values())))
            hole = max(getattr(hole, "geoms", [hole]), key=lambda g: g.area)
            fill = hole.difference(hole.buffer(-R, join_style=1).buffer(R, join_style=1))
        else:             # L: one quarter-circle fillet under the deck, sized to fit the stub
            qx, qz = 2 * half, TOP - 2 * half
            r = min(R, qz - (C[1] - half) - 1.0)
            fill = box(qx, qz - r, qx + r, qz).difference(Point(qx + r, qz - r).buffer(r, quad_segs=32)) if r > 1 else Polygon()
        body = unary_union([body, fill])
    if smooth:
        body = body.buffer(smooth, join_style=1).buffer(-smooth, join_style=1)
    parts = [body, HOOKP]
    if rest:
        parts += [box(-REST_TAB[0], RF, 0.01, RF + REST_TAB[1])]
    return unary_union(parts), z_floor


def evaluate_geom(geom, depth, width, bottom, rest):
    h = float(os.environ.get("FEA_H", "0.4"))
    m = Bracket(depth=depth, z_bottom=min(bottom - 6, -20.0), h=h, t=width, rest=rest)
    r = evaluate(m, contains_xy(geom, m.grid.xc, m.grid.zc), P=100.0)
    lim = {k: v / 9.81 for k, v in r["limits_N"].items()}
    tip = max(r["cases"]["uniform"]["tip_mm"], 1e-6)                 # mm of tip sag per 100 N, even load
    lim["sag"] = (depth / SAG_RATIO) / tip * 100.0 / 9.81
    return min(lim.values()), r["mass"], lim


def candidates(depth):
    lower_slot_top = RF + SLOT_OPEN
    out = []
    for sl in (20, 30, 45, 60):                                  # L-shapes: spine pad lengths
        if sl < 0.9 * depth + 20:
            out.append((f"L{sl}", dict(spine_len=sl)))
    for name, ang in (("T45", 45), ("T55", 55)):
        fz = TOP - depth * math.tan(math.radians(ang))
        if fz > lower_slot_top + 6:                              # foot must press on wall face above the next slot
            out.append((name, dict(foot_z=fz)))
    # into the next slot only once a 45 deg diagonal would reach it (steeper than that is wasteful)
    if TOP - depth <= lower_slot_top + 6:
        out.append(("slot", dict(rest=True)))
    return out


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


LIP_T = 1.3            # lip top width (2 lines); the inner face is chamfered 45 deg below that
LIP_X0 = 5.0           # side lips start this far from the wall (tilt-in clearance checked with tiltsim)


def to_part_lip(geom, width, depth, lip=0.0):
    """Extrude the profile `width` tall (print orientation). lip > 0 adds a chamfered lip of that height
    along the front edge and both side edges of the deck (side lips stop LIP_X0 short of the wall)."""
    from make_catalog import to_part
    from build123d import Plane, Polygon as BPoly, extrude, BuildSketch, Location
    if lip <= 0:
        return to_part(geom, width, width)
    h, t = lip, LIP_T
    front = Polygon([(depth - t - h, TOP), (depth, TOP), (depth, TOP + h), (depth - t, TOP + h)])
    front = front.union(box(depth - 3.5, TOP - 3.5, depth, TOP))          # square the rounded top-front corner under the lip
    part = to_part(unary_union([geom, front]), width, width)
    part = part.translate((0, 0, -part.bounding_box().min.Z))          # body spans z = 0..width
    for pts in (((TOP, 0), (TOP + h, 0), (TOP + h, t), (TOP, t + h)),
                ((TOP, width), (TOP + h, width), (TOP + h, width - t), (TOP, width - t - h))):
        with BuildSketch(Plane.YZ.offset(LIP_X0)) as sk:
            BPoly(*pts, align=None)
        part = part + extrude(sk.sketch, amount=depth - LIP_X0)
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
