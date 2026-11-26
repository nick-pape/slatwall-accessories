"""Organic printable parts from exact signed distance fields + marching cubes.

A part is a set of MEMBERS, each a 2D shape in the x/z plane (exact distance: capsules, bands, polygons)
extruded `h` along y (= print Z, profile on the bed) with its long edges rounded by the member's own
radius r -- r = half its thickness makes a round rod / tube. Bottom edges get a 45 deg teardrop keel
down to a flat on the bed so nothing overhangs. Members are joined with a smooth minimum (k = fillet
size). Then clearances are cut, bores subtracted (teardrop, apex up, crush ribs).
"""
import math
import numpy as np
import shapely
from shapely import contains_xy

S2 = math.sqrt(2.0)


# ---------- exact 2D distances (negative inside) ----------
def d_capsule(X, Z, p, q, R):
    p, q = np.asarray(p, float), np.asarray(q, float)
    pq = q - p; L2 = pq @ pq
    t = np.clip(((X - p[0]) * pq[0] + (Z - p[1]) * pq[1]) / L2, 0, 1)
    return np.hypot(X - p[0] - t * pq[0], Z - p[1] - t * pq[1]) - R


def d_halfplane(X, Z, p, n):
    """Distance to the half-plane {(x - p) . n <= 0} (n = outward unit normal)."""
    return (X - p[0]) * n[0] + (Z - p[1]) * n[1]


def d_poly(X, Z, poly):
    pts = shapely.points(X.ravel(), Z.ravel())
    d = shapely.distance(pts, poly.boundary).reshape(X.shape)
    return np.where(contains_xy(poly, X, Z), -d, d)


# ---------- 3D ----------
def rounded_extrusion(d2, r, h, y):
    """Extrude a 2D field over y in [0, h], rounding the edges with radius r, plus a 45 deg keel underneath."""
    q1 = d2 + r
    q2 = abs(y - h / 2) - h / 2 + r
    d = np.sqrt(np.maximum(q1, 0) ** 2 + np.maximum(q2, 0) ** 2) + np.minimum(np.maximum(q1, q2), 0) - r
    keel = np.maximum(np.maximum((d2 - y + r * (2 - S2)) / S2, d2), np.maximum(-y, y - r))
    return np.minimum(d, keel)


def smin(a, b, k):
    if k <= 0:
        return np.minimum(a, b)
    hh = np.clip(0.5 + 0.5 * (b - a) / k, 0, 1)
    return b * (1 - hh) + a * hh - k * hh * (1 - hh)


def bore_sdf(X, Z, b, p0, p1, R, rib_in=0.35, rib_r=0.8, ribs=(-90, 30, 150), roof=1.6):
    """Teardrop bore from p0 (open mouth) to p1 (bottom); b = y - axis height."""
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    L = np.linalg.norm(p1 - p0); u = (p1 - p0) / L; n = np.array([-u[1], u[0]])
    t = (X - p0[0]) * u[0] + (Z - p0[1]) * u[1]
    a = (X - p0[0]) * n[0] + (Z - p0[1]) * n[1]
    circ = np.sqrt(a * a + b * b) - R
    kite = np.maximum((np.abs(a) + b) / S2 - R, (np.abs(a) - b) / S2)
    tear = np.maximum(np.minimum(circ, kite), b - (R + roof))
    rib = np.full(a.shape, np.inf)
    for th in ribs:
        c = (R - rib_in + rib_r) * np.array([math.cos(math.radians(th)), math.sin(math.radians(th))])
        rib = np.minimum(rib, np.sqrt((a - c[0]) ** 2 + (b - c[1]) ** 2) - rib_r)
    d = np.maximum(tear, -rib)
    return np.maximum(d, np.maximum(-t - 1.0, t - L))


def build(bounds, h, members, k=5.0, res=0.2, cut2d=(), keep2d=None, add=(), bores=(), bore_R=9.2):
    """members / add: [(d2_fn(X, Z), r)]; members are smooth-unioned with k, `add` hard-unioned after cuts.
    cut2d: [d2_fn] regions removed through the full height; keep2d: d2_fn the part is clipped to.
    Returns a watertight trimesh in print coords (X = x, Y = z, Z = y in [0, h])."""
    import trimesh
    from skimage.measure import marching_cubes
    x0, z0, x1, z1 = bounds
    xs = np.arange(x0 - 3, x1 + 3, res); zs = np.arange(z0 - 3, z1 + 3, res)
    X, Z = np.meshgrid(xs, zs, indexing="ij")
    # One profile, one extrusion: smooth-union the 2D member fields (2D fillets), and blend each member's
    # edge radius by proximity so the rounding changes smoothly across joints (no grooves/dimples where
    # separately-rounded rods used to meet).
    D = [f(X, Z) for f, _ in members]
    P = D[0]
    for d2 in D[1:]:
        P = smin(P, d2, k)
    # Re-derive an exact distance from the blended outline with interior holes filled: a smin-filled
    # pocket only reads slightly negative, which made the rounding dip into a dimple there.
    from skimage.measure import find_contours
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    polys = [Polygon(np.c_[np.interp(c[:, 0], np.arange(len(xs)), xs), np.interp(c[:, 1], np.arange(len(zs)), zs)])
             for c in find_contours(P, 0.0) if len(c) > 3]
    polys = [q.buffer(0) for q in polys if q.is_valid or q.buffer(0).area > 0]
    outline = max(unary_union([Polygon(q.exterior) for q in polys if q.area > 1]).geoms
                  if hasattr(unary_union([Polygon(q.exterior) for q in polys if q.area > 1]), "geoms")
                  else [unary_union([Polygon(q.exterior) for q in polys if q.area > 1])], key=lambda q: q.area)
    P = d_poly(X, Z, Polygon(outline.exterior))
    Dm = np.minimum.reduce(D)
    W = [np.exp(-(d2 - Dm) / max(k, 1e-6)) for d2 in D]
    Rf = sum(w * r for w, (_, r) in zip(W, members)) / sum(W)
    Rf = np.minimum(Rf, h / 2 - 0.01)
    A = [(f(X, Z), r) for f, r in add]
    C = [f(X, Z) for f in cut2d]
    K = keep2d(X, Z) if keep2d else None
    ys = np.arange(-2 * res, h + 3 * res, res)
    vol = np.empty((len(xs), len(zs), len(ys)), np.float32)
    for j, y in enumerate(ys):
        d = rounded_extrusion(P, Rf, h, y)
        for c in C:
            d = np.maximum(d, -c)
        for d2, r in A:
            d = np.minimum(d, rounded_extrusion(d2, r, h, y))
        if K is not None:
            d = np.maximum(d, K)
        for p0, p1 in bores:
            d = np.maximum(d, -bore_sdf(X, Z, y - h / 2, p0, p1, bore_R))
        vol[:, :, j] = np.maximum(np.maximum(d, -y), y - h)          # blends bulge: clip to the slab
    verts, faces, _, _ = marching_cubes(vol, 0.0, spacing=(res, res, res), allow_degenerate=False)
    verts += [xs[0], zs[0], ys[0]]
    mesh = trimesh.Trimesh(verts, faces[:, ::-1], process=True)
    parts = mesh.split(only_watertight=False)
    if len(parts) > 1:
        mesh = max(parts, key=lambda p: abs(p.volume))
    if mesh.volume < 0:
        mesh.invert()
    mesh.vertices[:, 2] = np.maximum(mesh.vertices[:, 2], 0.0)
    return mesh
