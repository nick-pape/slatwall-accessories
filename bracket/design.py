"""Parametric 'hanging arch' bracket, the clean version of what the layout optimiser found:

  * deck chord along the top (z = NECK_TOP), carrying the shelf
  * compression ARCH from the deck tip curving down to a foot that bears on the wall face,
    arriving horizontally (the wall can only push, frictionless). The arch is a twin-wall
    "ladder": two perimeter walls S apart with zig-zag lacing -- buckling-proof per gram.
  * tension TIES fanning from the hook root down to the arch panel points
  * short POSTS from the arch panel points up to the deck chord

Geometry is 2D (as-mounted x-z plane) and is extruded `t` mm -- the bracket prints flat.
"""
import math
from dataclasses import dataclass, asdict, replace
import numpy as np
from shapely.geometry import LineString, Polygon, Point, box
from shapely.ops import unary_union
from shapely import contains_xy

from model import Bracket
from slathook import HOOK, NECK_TOP, hook_profile_pts

# Member widths are exact multiples of PrusaSlicer perimeters (0.6 HF nozzle, 0.15 mm layers):
# width(n) = w + (n-1) * spacing, spacing = w - layer*(1 - pi/4). Thin members then print as
# n continuous perimeter loops with no gap fill or infill -- the strongest thing a printer makes.
PERIM_W, LAYER = 0.60, 0.15
PERIM_S = PERIM_W - LAYER * (1 - math.pi / 4)


def perims(n):
    return PERIM_W + (n - 1) * PERIM_S


LINE = PERIM_S


@dataclass
class Params:
    depth: float = 200.0
    foot_z: float = -100.0      # height of the arch foot on the wall
    ctrl: float = 0.45          # arch Bezier control point at (ctrl*depth, foot_z): flatter -> larger
    S: float = 14.0             # twin-wall spacing (centre-to-centre)
    wall: float = perims(3)      # each arch wall (2 perimeters)
    lace: float = perims(2)      # lacing bars
    lace_pitch: float = 10.0    # distance between lacing nodes along the arch
    n_panels: int = 4           # tie/post panel points along the arch
    tie_w: float = perims(2)     # tension tie width
    post_w: float = perims(3)    # post width
    chord_h: float = 4.0        # deck chord depth (top of chord at NECK_TOP)
    t: float = 10.0             # truss print height = bracket width along the wall
    t_hook: float = 20.0        # hook + root block print height (taller = stronger hook)
    rest: bool = False          # foot sits in the next slot down (tab on its floor)
    spine_w: float = 0.0        # vertical member along the wall face, hook root -> foot (0 = none)


def bezier(p0, p1, p2, n=200):
    s = np.linspace(0, 1, n)[:, None]
    return (1 - s) ** 2 * p0 + 2 * (1 - s) * s * p1 + s ** 2 * p2


def strip(line, w):
    return line.buffer(w / 2, cap_style=2, join_style=2)


def geometry(p: Params):
    D = p.depth
    tip = np.array([D - p.S / 2, NECK_TOP - p.chord_h / 2])
    if p.rest:                                   # land the arch on the lower slot
        from slathook import SLOT_PITCH
        p = replace(p, foot_z=-SLOT_PITCH + p.S / 2 + p.wall + 1.0)
    foot = np.array([0.0, p.foot_z])
    ctrl = np.array([p.ctrl * D, p.foot_z])
    mid = bezier(foot, ctrl, tip)
    # offset the centreline +/- S/2 for the two walls
    tang = np.gradient(mid, axis=0); tang /= np.linalg.norm(tang, axis=1)[:, None]
    nrm = np.stack([-tang[:, 1], tang[:, 0]], 1)
    up, lo = mid + nrm * p.S / 2, mid - nrm * p.S / 2
    shapes = [strip(LineString(up), p.wall), strip(LineString(lo), p.wall)]
    # zig-zag lacing
    arc = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(mid, axis=0), axis=1))])
    n_l = max(2, int(round(arc[-1] / p.lace_pitch)))
    idx = [int(np.argmin(np.abs(arc - k * arc[-1] / n_l))) for k in range(n_l + 1)]
    for k in range(n_l):
        a, b = idx[k], idx[k + 1]
        A, B = (up[a], lo[b]) if k % 2 == 0 else (lo[a], up[b])
        shapes.append(strip(LineString([A, B]), p.lace))
    shapes.append(strip(LineString([up[0], lo[0]]), p.lace))
    shapes.append(strip(LineString([up[-1], lo[-1]]), p.lace))
    # deck chord
    shapes.append(box(0, NECK_TOP - p.chord_h, D, NECK_TOP))
    # tip block joining chord and arch end
    shapes.append(box(D - p.S - p.wall, NECK_TOP - p.chord_h - p.S * 0.6, D, NECK_TOP))
    # foot pad on the wall face
    shapes.append(box(0, p.foot_z - p.S / 2 - p.wall, 6.0, p.foot_z + p.S / 2 + p.wall))
    # hook root block
    root = box(0, -8.0, 8.0, NECK_TOP)
    shapes.append(root)
    hook_anchor = np.array([3.0, -4.0])
    # panel points on the arch (upper wall), ties from the hook root, posts up to the chord
    for k in range(1, p.n_panels + 1):
        s = k / (p.n_panels + 1)
        i = int(np.argmin(np.abs(arc - s * arc[-1])))
        P = up[i]
        if P[1] < NECK_TOP - p.chord_h - 2:
            shapes.append(strip(LineString([P, (P[0], NECK_TOP - p.chord_h / 2)]), p.post_w))
            shapes.append(strip(LineString([hook_anchor, P]), p.tie_w))
            shapes.append(Point(P).buffer(p.post_w))                # node boss
    if p.spine_w > 0:
        shapes.append(box(0, p.foot_z, p.spine_w, 0.0))
    hook = Polygon(hook_profile_pts(0.0, 0.0, NECK_TOP, HOOK))
    body = unary_union(shapes).intersection(box(0, -1e3, D, NECK_TOP))  # nothing behind/above
    parts = [body, hook]
    if p.rest:
        from catalog import rest_foot
        parts.append(rest_foot())
    return unary_union(parts)


def thick_zone(p: Params):
    """Region printed at t_hook: the hook, its root block and the chord's first 15 mm."""
    hook = Polygon(hook_profile_pts(0.0, 0.0, NECK_TOP, HOOK))
    return unary_union([hook, box(0, -8.0, 15.0, NECK_TOP)])


def mask(m: Bracket, geom):
    g = m.grid
    return contains_xy(geom, g.xc, g.zc)


def thickness_factor(m: Bracket, p: Params):
    g = m.grid
    return np.where(contains_xy(thick_zone(p), g.xc, g.zc), p.t_hook / p.t, 1.0)


def area_mass(geom, t, rho=1.27e-3):
    return geom.area * t * rho


def to_part(p: Params, tol=0.05):
    """3D part in PRINT orientation: profile flat on the bed (bed = as-mounted x-z plane),
    truss t tall, hook zone t_hook tall, all standing on the bed (no supports needed)."""
    from build123d import Face, Wire, Vector, extrude, Part
    def face(poly):
        poly = poly.simplify(tol)
        ext = Wire.make_polygon([Vector(x, z, 0) for x, z in poly.exterior.coords[:-1]], close=True)
        holes = [Wire.make_polygon([Vector(x, z, 0) for x, z in r.coords[:-1]], close=True)
                 for r in poly.interiors]
        return Face(ext, holes)
    def solid(geom, h):
        geoms = getattr(geom, "geoms", [geom])
        out = None
        for gg in geoms:
            e = extrude(face(gg), amount=h)
            out = e if out is None else out + e
        return out
    g = geometry(p)
    thick = g.intersection(thick_zone(p))
    return solid(g, p.t) + solid(thick, p.t_hook)
