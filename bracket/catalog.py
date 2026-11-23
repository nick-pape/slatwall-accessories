"""Bracket design catalog -- every design is a 2D profile evaluated with the same FEA.

Styles: beautiful (architecture), optimized, minimalist, organic. All share the hook, the hook
root block, the deck along the top, and (where noted) the REST tab that sits in the next slot
down and carries weight on that slot's floor.
"""
import math
import numpy as np
from shapely.geometry import LineString, Polygon, Point, box, MultiPolygon
from shapely.ops import unary_union, polylabel

from slathook import HOOK, NECK_TOP, SLOT_PITCH, hook_profile_pts
from model import Bracket, REST_TAB
from design import perims, bezier, strip, Params, geometry as arch_geometry

D = 200.0
TOP = NECK_TOP
H_ = 0.4
RF = -SLOT_PITCH          # lower slot floor (exact; the FEA grid snaps its own support line)
HOOKP = Polygon(hook_profile_pts(0.0, 0.0, NECK_TOP, HOOK))
ROOT = box(0, -8.0, 8.0, TOP)


def thick_zone():
    return unary_union([HOOKP, box(0, -8.0, 15.0, TOP)])


def rest_foot():
    """Pad on the wall face spanning the lower slot + the tab that sits in it."""
    return unary_union([box(0, RF - 6, 8, RF + 13), box(-REST_TAB[0], RF, 0.01, RF + REST_TAB[1])])


def finish(shapes, rest=True, smooth=0.0):
    body = unary_union(shapes).intersection(box(0, -1e3, D, TOP))
    if smooth:
        body = body.buffer(smooth, join_style=1).buffer(-smooth, join_style=1)    # fillet inside corners
    parts = [body, HOOKP, ROOT]
    if rest:
        parts.append(rest_foot())
    return unary_union(parts)


def tapered(curve, w0, w1):
    """Polygon of a centreline whose width goes linearly from w0 to w1."""
    c = np.asarray(curve)
    t = np.gradient(c, axis=0); t /= np.linalg.norm(t, axis=1)[:, None]
    n = np.stack([-t[:, 1], t[:, 0]], 1)
    w = np.linspace(w0, w1, len(c))[:, None] / 2
    return Polygon(np.vstack([c + n * w, (c - n * w)[::-1]])).buffer(0)


def chord(h):
    return box(0, TOP - h, D, TOP)


FOOT = np.array([5.0, RF + 6.0])          # where compression members land at the lower slot


# ----------------------------------------------------------------- minimalist
def minimal(w_strut=6.0, w_chord=5.0):
    """Two bars: the deck and one straight strut into the lower slot."""
    tip = np.array([D - 3, TOP - w_chord / 2])
    return finish([chord(w_chord), strip(LineString([FOOT, tip]), w_strut), box(D - 8, TOP - 10, D, TOP)], smooth=1.5)


# ----------------------------------------------------------------- beautiful
def salginatobel(n_cols=8, rib0=8.0, rib1=3.5, ch=3.5, col_w=perims(3)):
    """Maillart's Salginatobel deck arch: a slim rib that thickens toward the springing,
    evenly spaced spandrel columns up to a thin deck."""
    tip = np.array([D - 3, TOP - ch])
    rib = bezier(FOOT, np.array([0.42 * D, FOOT[1] - 2]), tip, 240)
    shapes = [chord(ch), tapered(rib, rib0, rib1)]
    for k in range(1, n_cols + 1):
        x = k * (D - 10) / (n_cols + 1) + 4
        i = np.argmin(np.abs(rib[:, 0] - x))
        z = rib[i, 1]
        if z < TOP - ch - 3:
            shapes.append(box(x - col_w / 2, z, x + col_w / 2, TOP - ch + 0.1))
    return finish(shapes, smooth=1.2)


def victorian(ch=4.0, post=5.0, brace=5.0, ring=perims(3)):
    """Cast-iron railway bracket: wall post, concave quarter-ellipse sweep, rings in the spandrel."""
    cz = FOOT[1]
    a, b = D - post, TOP - cz
    th = np.linspace(0, np.pi / 2, 200)
    sweep = np.stack([D - a * np.cos(th), cz + b * np.sin(th)], 1)
    shapes = [chord(ch), box(0, RF - 6, post, TOP), tapered(sweep, brace * 1.4, brace)]
    region = Polygon(np.vstack([[[post, TOP - ch]], sweep[::-1][:-1], [[post, cz]]])).buffer(-brace / 2)
    rings = []
    for _ in range(3):
        if region.is_empty:
            break
        big = max(getattr(region, "geoms", [region]), key=lambda g: g.area)
        c = polylabel(big, tolerance=0.2)
        r = big.exterior.distance(c)
        if r < 6:
            break
        rings.append(Point(c).buffer(r + ring / 2).difference(Point(c).buffer(r - ring / 2)))
        region = region.difference(Point(c).buffer(r + 1.0))
    return finish(shapes + rings, smooth=1.0)


def forth(n=6, ch=3.0, bottom=5.0, lattice=perims(2), post_w=perims(3)):
    """Forth Bridge cantilever: deep curved bottom chord, straight top chord, X-braced panels."""
    tip = np.array([D - 3, TOP - ch])
    bot = bezier(FOOT, np.array([0.55 * D, FOOT[1] + 6]), tip, 240)
    shapes = [chord(ch), tapered(bot, bottom * 1.3, bottom * 0.8)]
    xs = np.linspace(8, D - 12, n + 1)
    zb = [bot[np.argmin(np.abs(bot[:, 0] - x)), 1] for x in xs]
    for k in range(n + 1):
        shapes.append(strip(LineString([(xs[k], zb[k]), (xs[k], TOP - ch / 2)]), post_w))
    for k in range(n):
        shapes.append(strip(LineString([(xs[k], zb[k]), (xs[k + 1], TOP - ch / 2)]), lattice))
        shapes.append(strip(LineString([(xs[k], TOP - ch / 2), (xs[k + 1], zb[k + 1])]), lattice))
    return finish(shapes, smooth=0.8)


# ----------------------------------------------------------------- optimized
def hanging_arch(variant="search_T15.json", **kw):
    """The tuned hanging arch (layout optimiser + parameter search)."""
    import json
    from pathlib import Path
    best = json.load(open(Path(__file__).parent / "out" / variant))["best"]
    best.update(kw)
    p = Params(**best)
    return unary_union([arch_geometry(p), HOOKP]), p


def twin_triangle(S=10.0, wall=perims(3), lace=perims(2), lace_pitch=8.0, n_posts=5,
                  post_w=perims(2), ch=3.0):
    """Straight twin-wall ladder strut from the deck tip into the lower slot rest, posts to the deck."""
    tip = np.array([D - S / 2 - 1, TOP - ch - S * 0.3])
    foot = FOOT + [S / 2, 0]
    L = np.linalg.norm(tip - foot)
    u = (tip - foot) / L
    nrm = np.array([-u[1], u[0]])
    shapes = [chord(ch), box(D - S - 4, TOP - ch - S, D, TOP), Point(foot).buffer(S * 0.8)]
    A0, A1 = foot + nrm * S / 2, tip + nrm * S / 2
    B0, B1 = foot - nrm * S / 2, tip - nrm * S / 2
    shapes += [strip(LineString([A0, A1]), wall), strip(LineString([B0, B1]), wall)]
    k = max(2, int(round(L / lace_pitch)))
    for i in range(k):
        s0, s1 = i / k, (i + 1) / k
        P = (A0 + (A1 - A0) * s0, B0 + (B1 - B0) * s1) if i % 2 == 0 else (B0 + (B1 - B0) * s0, A0 + (A1 - A0) * s1)
        shapes.append(strip(LineString(P), lace))
    for i in range(1, n_posts + 1):
        P = A0 + (A1 - A0) * i / (n_posts + 1)
        if P[1] < TOP - ch - 3:
            shapes.append(strip(LineString([P, (P[0], TOP - ch / 2)]), post_w))
    return finish(shapes, smooth=1.0)


# ----------------------------------------------------------------- organic
def gaudi_tree(levels=3, leaf_w=perims(3), ch=3.0, grow=0.62, curl=0.18):
    """Branching column like the Sagrada Familia's tree columns: a trunk from the lower-slot rest
    splitting into curved branches that hold the deck at evenly spaced points."""
    n = 2 ** levels
    leaves = [np.array([12 + (D - 18) * (i + 0.5) / n, TOP - ch / 2]) for i in range(n)]
    shapes = [chord(ch)]
    nodes = leaves
    zs = np.linspace(TOP - ch, FOOT[1] + 22, levels + 1)[1:]
    for lev in range(levels):
        parents = []
        for i in range(0, len(nodes), 2):
            a, b = nodes[i], nodes[i + 1]
            pz = zs[lev]
            px = (a[0] + b[0]) / 2 * (1 - 0.25 * (lev + 1) / levels) + FOOT[0] * 0.25 * (lev + 1) / levels
            parents.append(np.array([px, pz]))
        nlev = 2 ** (lev + 1)       # leaves under each parent
        for j, P in enumerate(parents):
            for C in (nodes[2 * j], nodes[2 * j + 1]):
                mid = (P + C) / 2 + np.array([-(C - P)[1], (C - P)[0]]) * curl * (1 if C[0] > P[0] else -1)
                w0 = leaf_w * nlev ** grow
                w1 = leaf_w * (nlev / 2) ** grow
                shapes.append(tapered(bezier(P, mid, C, 60), w0, w1))
                shapes.append(Point(P).buffer(w0 * 0.6))
        nodes = parents
    root = nodes[0]
    trunk_w = leaf_w * n ** grow
    shapes.append(tapered(bezier(FOOT, (FOOT + root) / 2 + [6, -6], root, 60), trunk_w * 1.15, trunk_w))
    return finish(shapes, smooth=2.0)


def bone(npz="out/bone_simp.npz", sigma=1.2, level=0.5, ch=3.0):
    """Topology-optimised (SIMP, with the rest support), density smoothed into a bone-like form."""
    from scipy.ndimage import gaussian_filter
    from skimage import measure
    d = np.load(npz)
    m = Bracket(depth=float(d["depth"]), z_bottom=float(d["z_bottom"]), h=float(d["h"]), t=float(d["t"]), rest=True)
    g = m.grid
    f = gaussian_filter(d["xp"].reshape(g.nz, g.nx), sigma / g.h)
    polys = []
    for c in measure.find_contours(np.pad(f, 1), level):
        z = g.z0 + (c[:, 0] - 1 + 0.5) * g.h
        x = g.x0 + (c[:, 1] - 1 + 0.5) * g.h
        if len(c) > 8:
            polys.append(Polygon(np.stack([x, z], 1)).buffer(0))
    # even-odd: holes are contours inside others
    polys.sort(key=lambda p: -p.area)
    shape = Polygon()
    for p in polys:
        shape = shape.symmetric_difference(p)
    shape = shape.buffer(0.6).buffer(-0.6)
    g = finish([shape, chord(ch)], smooth=1.0)
    return unary_union([q for q in getattr(g, "geoms", [g]) if q.area > 150])     # drop floating islands


DESIGNS = {
    "minimal_two_bars":   ("minimalist", minimal, True),
    "salginatobel":       ("beautiful", salginatobel, True),
    "victorian":          ("beautiful", victorian, True),
    "forth_bridge":       ("beautiful", forth, True),
    "hanging_arch":       ("optimized", None, False),
    "hanging_arch_rest":  ("optimized", None, True),
    "twin_triangle":      ("optimized", twin_triangle, True),
    "gaudi_tree":         ("organic", gaudi_tree, True),
    "bone":               ("organic", bone, True),
}
