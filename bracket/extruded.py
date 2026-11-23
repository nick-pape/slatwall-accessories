"""Second study: the WHOLE SHELF is one extruded profile (profile on the bed, printed W tall).

Every mm of shelf width carries its own share of the load, the hook and rest tab run the full
width, and the deck is part of the profile. Members are at least 2 perimeters (0.40 mm layers).
Sized for TARGET_KG on a W x 200 mm shelf.

    uv run python extruded.py            # size every design, write out/extruded_sized.json
"""
import json, math, sys, warnings
warnings.filterwarnings("ignore")
from concurrent.futures import ProcessPoolExecutor
import numpy as np
from shapely.geometry import LineString, box, Point
from shapely import contains_xy

W = 200.0
TARGET_KG = 20.0
W040, L040 = 0.68, 0.40
S040 = W040 - L040 * (1 - math.pi / 4)
P = lambda n: round(W040 + (n - 1) * S040, 4)       # n perimeters at 0.40 mm layers


def right_triangle(deck=4.0, diag=4.0, back=0.0, n_posts=0, post_w=P(2)):
    from catalog import finish, chord, strip, FOOT, D, TOP
    tip = np.array([D - 3, TOP - deck / 2])
    shapes = [chord(deck), strip(LineString([FOOT, tip]), diag), box(D - 8, TOP - deck - 6, D, TOP)]
    if back > 0:
        shapes.append(box(0, FOOT[1], back, 0.0))
    for i in range(1, n_posts + 1):
        Q = FOOT + (tip - FOOT) * i / (n_posts + 1)
        if Q[1] < TOP - deck - 3:
            shapes.append(strip(LineString([Q, (Q[0], TOP - deck / 2)]), post_w))
    return finish(shapes, smooth=1.5)


def sierpinski(levels=2, deck=P(2), diag=P(2), web=P(2), back=0.0, skew=0.5, grade=False, web_fine=None, coarse=2):
    """web: width of the first `coarse` levels; web_fine: width of deeper levels (None = same)."""
    """Triangle deck / diagonal / wall, filled with a recursive midpoint web (Sierpinski-like):
    every corner triangle is subdivided again, so the thin outer members are braced at many
    points. `skew` moves the subdivision points along each edge (0.5 = classic Sierpinski)."""
    from catalog import finish, chord, strip, FOOT, D, TOP
    A = np.array([4.0, TOP - deck / 2])          # wall end of the deck
    B = np.array([D - 3, TOP - deck / 2])        # deck tip
    C = FOOT.copy()                              # foot at the lower-slot rest
    lines = []
    def rec(a, b, c, n):
        if n == 0:
            return
        ab, bc, ca = a + (b - a) * skew, b + (c - b) * skew, c + (a - c) * skew
        lvl = levels - n + 1
        lines.extend([(ab, bc, lvl), (bc, ca, lvl), (ca, ab, lvl)])
        if grade:          # graded: only keep subdividing the triangles that touch the diagonal (b-c)
            rec(ab, b, bc, n - 1); rec(ca, bc, c, n - 1)
        else:
            rec(a, ab, ca, n - 1); rec(ab, b, bc, n - 1); rec(ca, bc, c, n - 1)
    rec(A, B, C, levels)
    shapes = [chord(deck), strip(LineString([C, B]), diag), box(D - 8, TOP - deck - 6, D, TOP)]
    if back > 0:
        shapes.append(box(0, C[1], back, 0.0))
    shapes += [strip(LineString([u, v]), web if (web_fine is None or lv <= coarse) else web_fine) for u, v, lv in lines]
    return finish(shapes, smooth=1.0)


def ladder(p0, p1, S, wall, lace, pitch):
    """Twin-wall member from p0 to p1 (centreline): two walls S apart + zig-zag lacing."""
    from catalog import strip
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


def twin_both(S=8.0, wall=P(2), lace=P(2), lace_pitch=12.0, smooth=1.0, node_r=0.0, spine=0.0, node_len=0.0,
              depth=200.0):
    """Twin-wall ladder for BOTH the deck and the diagonal, same spacing, walls, lacing and pitch.
    The deck becomes a sandwich panel (stiff underfoot), the diagonal a buckling-proof strut."""
    from catalog import finish, FOOT, TOP
    D = depth
    deck_c = TOP - wall / 2 - S / 2                      # deck centreline: top skin flush with the deck top
    tip = np.array([D - S / 2 - 1, deck_c])
    foot = FOOT + [S / 2, 0]
    shapes = ladder([wall / 2, deck_c], [D - wall / 2, deck_c], S, wall, lace, lace_pitch)
    shapes += ladder(foot, tip, S, wall, lace, lace_pitch)
    if node_r > 0:
        # rounded tip node: convex hull of where the two ladders meet, corners rounded (also rounds the
        # acute front corner) -- replaces the square tip block
        from shapely.ops import unary_union as _uu
        reach = node_len if node_len else S + 18
        near = _uu(shapes).intersection(box(D - reach, deck_c - reach, D, TOP))
        node = near.convex_hull.buffer(-node_r, join_style=1).buffer(node_r, join_style=1)
        shapes = [sh.intersection(box(-1e3, -1e3, D, 1e3)) for sh in shapes] + [node, Point(foot).buffer(S * 0.8)]
        clip_nose = node
    else:
        shapes += [box(D - wall, deck_c - S / 2, D, TOP), Point(foot).buffer(S * 0.8), box(D - S - 2, deck_c - S / 2 - 2, D, TOP)]
    if spine > 0:
        shapes.append(box(0, foot[1], spine, 0.0))
    g = finish(shapes, smooth=smooth)
    if node_r > 0:      # anything poking out beyond the rounded nose (outer diagonal wall) is trimmed
        from shapely.ops import unary_union as _uu
        front = box(D - (node_len if node_len else S + 18), -1e3, D + 1, 1e3)
        g = _uu([g.difference(front), g.intersection(front).intersection(clip_nose.buffer(0.01)),
                 g.intersection(front).difference(clip_nose.buffer(0.01).convex_hull)])
    return g


def tri_ladder(depth=200.0, S=6.0, wall=P(2), lace=P(2), lace_pitch=10.0, smooth=0.4, joint_r=2.0, joint_reach=None):
    """Three identical twin-wall ladders -- deck, diagonal, wall spine -- three compact rounded joints,
    the hook at the top joint and the rest tab at the bottom joint. Nothing else."""
    from shapely.ops import unary_union
    from shapely.geometry import Polygon
    from catalog import finish, RF, TOP, HOOKP
    from model import REST_TAB
    half = S / 2 + wall / 2                       # centreline -> outer face of a ladder
    A = np.array([half, TOP - half])              # top joint (hook)
    B = np.array([depth - half, TOP - half])      # nose
    C = np.array([half, RF + half])               # bottom joint: its underside sits on the rest-tab line
    members = {"deck": ladder(A, B, S, wall, lace, lace_pitch),
               "diag": ladder(C, B, S, wall, lace, lace_pitch),
               "spine": ladder(C, A, S, wall, lace, lace_pitch)}
    allm = unary_union(sum(members.values(), []))
    R = joint_reach or (S + wall + 3)
    joints = []
    for V in (A, B, C):
        local = allm.intersection(Point(V).buffer(R))
        joints.append(local.convex_hull.buffer(-joint_r, join_style=1).buffer(joint_r, join_style=1))
    tab = box(-REST_TAB[0], RF, 0.01, RF + REST_TAB[1])
    body = unary_union([allm] + joints).intersection(box(0, -1e3, depth, TOP))
    if smooth:
        body = body.buffer(smooth, join_style=1).buffer(-smooth, join_style=1)
    root = box(0, 0, 2 * half, TOP).intersection(Point(A).buffer(R)).convex_hull      # hook bar -> joint A, solid
    foot = box(0, RF, 2 * half, RF + REST_TAB[1])                                       # tab fully embedded
    return unary_union([body, HOOKP, tab, root, foot])


def twin_triangle(**kw):
    from catalog import twin_triangle as tt
    return tt(**kw)


def hanging_arch(**kw):
    from design import Params, geometry
    p = Params(rest=True, t=W, t_hook=W, **kw)
    return geometry(p)


DESIGNS = {
    "tri_ladder": (tri_ladder, {"S": [5, 6, 8, 10], "lace_pitch": [8, 10, 12, 16], "joint_r": [1.0, 2.0, 3.0]}),
    "twin_both": (twin_both, {"S": [4, 5, 6, 8, 10, 12], "wall": [P(1), P(2), P(3)], "lace": [P(1), P(2)],
                              "lace_pitch": [6, 8, 10, 12, 16, 20]}),
    "sierpinski": (sierpinski, {"levels": [3, 4, 5], "deck": [P(1), P(2), P(3), 2.5], "diag": [P(1), P(2), P(3), 2.5, 3, 4],
                                "web": [P(1), P(2)], "back": [0.0, P(2)], "skew": [0.4, 0.5, 0.6],
                                "grade": [False, True], "web_fine": [None, P(1), P(2)], "coarse": [1, 2, 3]}),
    "right_triangle": (right_triangle, {"deck": [1.27, 1.87, 2.5, 3, 4, 5, 6], "diag": [1.87, 2.5, 3, 4, 5, 6, 8],
                                        "back": [0.0, P(2), P(3)]}),
    "triangle_posts": (right_triangle, {"deck": [1.27, 1.87, 2.5, 3, 4], "diag": [1.87, 2.5, 3, 4, 5, 6],
                                        "n_posts": [1, 2, 3, 4, 6], "post_w": [P(2), P(3), P(4)], "back": [0.0, P(2)]}),
    "twin_triangle": (twin_triangle, {"S": [6, 8, 10, 12, 16], "wall": [P(2), P(3)], "lace": [P(2)],
                                      "lace_pitch": [8, 12, 16, 24], "n_posts": [0, 2, 3, 5], "post_w": [P(2), P(3)],
                                      "ch": [1.27, 1.87, 2.5, 3, 4]}),
    "hanging_arch": (hanging_arch, {"S": [6, 8, 12], "ctrl": [0.2, 0.3, 0.45], "n_panels": [2, 3, 5],
                                    "wall": [P(2), P(3)], "lace": [P(2)], "lace_pitch": [8, 12, 16],
                                    "tie_w": [P(2), P(3)], "post_w": [P(2), P(3)], "chord_h": [1.27, 1.87, 2.5, 3, 4]}),
}
START = {
    "tri_ladder": dict(S=6, wall=P(2), lace=P(2), lace_pitch=10, smooth=0.4, joint_r=2.0),
    "twin_both": dict(S=6, wall=P(2), lace=P(2), lace_pitch=12),
    "sierpinski": dict(levels=4, deck=P(2), diag=P(2), web=P(2), back=0.0, skew=0.5, grade=True, web_fine=P(1), coarse=2),
    "right_triangle": dict(deck=4, diag=4, back=0.0),
    "triangle_posts": dict(deck=2.5, diag=4, n_posts=3, post_w=P(2), back=0.0),
    "twin_triangle": dict(S=10, wall=P(2), lace=P(2), lace_pitch=12, n_posts=3, post_w=P(2), ch=2.5),
    "hanging_arch": dict(S=8, ctrl=0.3, n_panels=5, wall=P(2), lace=P(2), lace_pitch=12, tie_w=P(2), post_w=P(2), chord_h=2.5),
}


def score(args):
    name, kw = args
    kw = dict(kw)
    width = kw.pop("width", W)              # shelf width along the wall = print height
    import warnings; warnings.filterwarnings("ignore")
    from model import Bracket
    from evaluate import evaluate
    from catalog import D
    try:
        geom = DESIGNS[name][0](**kw)
        m = Bracket(depth=kw.get("depth", D), z_bottom=-130.0, h=float(__import__("os").environ.get("FEA_H", "0.4")),
                    t=width, rest=True)
        r = evaluate(m, contains_xy(geom, m.grid.xc, m.grid.zc), P=100.0)
        kg, mass = r["allow_N"] / 9.81, r["mass"]
        lim = {k: v / 9.81 for k, v in r["limits_N"].items()}
    except Exception as e:
        return dict(obj=1e9, err=repr(e))
    return dict(obj=mass * max(1.0, TARGET_KG / max(kg, 1e-3)) ** 2, kg=kg, mass=mass, lim=lim,
                area=r["area"])


def search(name, ex, log=print):
    space = DESIGNS[name][1]
    best = dict(START[name])
    cur = score((name, best)); seen = {json.dumps(best, sort_keys=True)}
    for rnd in range(4):
        improved = False
        for k, vals in space.items():
            cands = [dict(best, **{k: v}) for v in vals if v != best[k]]
            cands = [c for c in cands if json.dumps(c, sort_keys=True) not in seen]
            for c, res in zip(cands, ex.map(score, [(name, c) for c in cands])):
                seen.add(json.dumps(c, sort_keys=True))
                if res["obj"] < cur["obj"] - 1e-6:
                    cur, best, improved = res, c, True
        log(f"{name:15s} round {rnd}: {cur.get('mass', 0):6.1f} g solid-equivalent, {cur.get('kg', 0):5.1f} kg "
            f"({cur.get('kg', 0) / max(cur.get('mass', 1), 1e-9):.3f} kg/g) "
            f"{ {k: round(v, 1) for k, v in cur.get('lim', {}).items()} } {best}")
        if not improved:
            break
    return dict(best=best, result=cur)


if __name__ == "__main__":
    names = sys.argv[1:] or list(DESIGNS)
    out = {}
    with ProcessPoolExecutor(5) as ex:
        for n in names:
            out[n] = search(n, ex, log=lambda s: print(s, flush=True))
            prev = json.load(open("out/extruded_sized.json")) if __import__("os").path.exists("out/extruded_sized.json") else {}
            prev.update(out)
            json.dump(prev, open("out/extruded_sized.json", "w"), indent=1, default=float)
    print("DONE", flush=True)
