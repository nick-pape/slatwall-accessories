"""Shelf generator geometry: pure Python (numpy + shapely), no CAD kernel and no solver.

Shared by the CLI (shelf_gen.py, which sizes each candidate with FEA) and the browser generator
(site/shelf, Pyodide), which picks the design from a precomputed capacity table
(shelf_table.py -> site/shelf/table.json) instead of solving.

Coordinates: x = out from the wall face (x = 0), z = up, hook bar on the slot bottom (z = 0).
The part prints lying on its side: this profile on the bed, extruded `width` tall.
"""
import math
import numpy as np
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

from slathook.profile import NECK_TOP, SLOT_PITCH, SLOT_OPEN, HOOK, hook_profile_pts

TOP = NECK_TOP                 # deck top = top of the hook bar (nothing in front of the wall may rise above it)
RF = -SLOT_PITCH               # lower slot floor
HOOKP = Polygon(hook_profile_pts(0.0, 0.0, NECK_TOP, HOOK))
REST_TAB = (4.0, 7.0)          # rest tab: depth into the lower slot, height (slot is 10 open)

W040, L040 = 0.68, 0.40
S040 = W040 - L040 * (1 - math.pi / 4)
P = lambda n: round(W040 + (n - 1) * S040, 4)       # n perimeters at 0.40 mm layers

SIZES = [(2, 6.0), (2, 8.0), (3, 6.0), (3, 8.0), (3, 10.0), (4, 10.0)]   # (perimeters, ladder spacing), light -> heavy
LIP_T = 1.3            # lip top width (2 lines); the inner face is chamfered 45 deg below that
LIP_X0 = 5.0           # side lips start this far from the wall (tilt-in clearance checked with tiltsim)


def strip(line, w):
    return line.buffer(w / 2, cap_style=2, join_style=2)


def ladder(p0, p1, S, wall, lace, pitch):
    """Twin-wall member from p0 to p1 (centreline): two walls S apart + zig-zag lacing."""
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    L = np.linalg.norm(p1 - p0); u = (p1 - p0) / L; nrm = np.array([-u[1], u[0]])
    A0, A1, B0, B1 = p0 + nrm * S / 2, p1 + nrm * S / 2, p0 - nrm * S / 2, p1 - nrm * S / 2
    shapes = [strip(LineString([A0, A1]), wall), strip(LineString([B0, B1]), wall)]
    k = max(2, int(round(L / pitch)))
    for i in range(k):
        s0, s1 = i / k, (i + 1) / k
        a, b = (A0 + (A1 - A0) * s0, B0 + (B1 - B0) * s1) if i % 2 == 0 else (B0 + (B1 - B0) * s0, A0 + (A1 - A0) * s1)
        shapes.append(strip(LineString([a, b]), lace))
    return shapes


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


def design(name, depth, S, perims):
    """Profile of candidate `name` (from candidates()) at this size -> (shapely geometry, bottom z)."""
    kw = dict(candidates(depth))[name]
    return frame(depth, S=S, perims=perims, **kw)


def lip_profile(depth, lip):
    """2D piece added to the profile for the front lip (empty if lip <= 0)."""
    if lip <= 0:
        return Polygon()
    h, t = lip, LIP_T
    front = Polygon([(depth - t - h, TOP), (depth, TOP), (depth, TOP + h), (depth - t, TOP + h)])
    return front.union(box(depth - 3.5, TOP - 3.5, depth, TOP))          # square the rounded top-front corner under the lip


def side_lips(width, lip):
    """Side lips as (quad in (profile z, print Z), x from, x to): prisms run along x, out from the wall."""
    if lip <= 0:
        return []
    h, t = lip, LIP_T
    return [(((TOP, 0), (TOP + h, 0), (TOP + h, t), (TOP, t + h)), LIP_X0),
            (((TOP, width), (TOP + h, width), (TOP + h, width - t), (TOP, width - t - h)), LIP_X0)]


def pick(table, width, depth, load_kg):
    """Choose the design from a capacity table (shelf_table.py) the way generate() does with live FEA:
    per candidate the first size (light -> heavy) that carries the load, then the lightest of those.
    Between tabulated depths both neighbours must pass (capacity is taken as the lower of the two).
    Returns dict(name, perims, S, kg, grams) or None."""
    import bisect
    ds = table["depths"]
    if not ds[0] <= depth <= ds[-1]:
        return None
    j = min(max(bisect.bisect_right(ds, depth) - 1, 0), len(ds) - 2) if len(ds) > 1 else 0
    lo, hi = ds[j], ds[min(j + 1, len(ds) - 1)]
    f = 0.0 if hi == lo else (depth - lo) / (hi - lo)
    rows = {}
    for d in {lo, hi}:
        for r in table["rows"][str(d)]:
            rows.setdefault((r["name"], r["perims"], r["S"]), {})[d] = r
    best = None
    for name, _ in candidates(depth):
        for perims, S in SIZES:
            rr = rows.get((name, perims, S), {})
            if len(rr) < len({lo, hi}):
                break                                              # not a candidate at a neighbouring depth
            kg = min(r["kg_per_mm"] for r in rr.values()) * width
            g = (rr.get(lo, rr.get(hi))["g_per_mm"] * (1 - f) + rr.get(hi, rr.get(lo))["g_per_mm"] * f) * width
            if kg >= load_kg:
                if best is None or g < best["grams"]:
                    best = dict(name=name, perims=perims, S=S, kg=kg, grams=g)
                break
    return best
