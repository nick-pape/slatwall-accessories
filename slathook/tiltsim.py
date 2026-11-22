"""2D tilt-in simulator for slatwall hooks.  Y = out of wall (face at 0), Z = up.

BFS over (theta, dy, dz) poses from the seated pose to fully outside the wall: if the hook
can get out, it can go in. Use it to screen a new hook shape before printing it:

    uv run python -m slathook.tiltsim                  # checks slathook.HOOK
    from slathook.tiltsim import check; check(my_hook_dict)
"""
import math, collections
from shapely.geometry import Polygon, LineString, box
from shapely import affinity
from shapely.prepared import prep

SLOT = 10.0

def wall(lip, cav_back=15.5, cav_top=16.5):
    return (box(-60, -60, 0, 0)                       # lower slat + cavity floor
            .union(box(-lip, SLOT, 0, 80))            # lip + upper slat face
            .union(box(-60, cav_top, -lip, 80))       # above cavity
            .union(box(-60, -60, -cav_back, 80)))     # back of cavity

def official_hook(wire=2.5):
    # centreline from the photo: vertical bar in front of the face, neck back 15, riser leaning fwd
    r = wire / 2
    pts = [(r, -25), (r, r), (-15 + r, r), (-8.5 - r, 15 - r)]
    return LineString(pts).buffer(r, join_style=2)

def can_insert(part, lip, step=0.5, dth=2.0, **kw):
    w = prep(wall(lip, **kw))
    part = part.buffer(-0.1)            # 0.1 mm clearance all round
    cache = {}
    def free(s):
        if s not in cache:
            th, iy, iz = s
            g = affinity.translate(affinity.rotate(part, th * dth, origin=(0, 0)), iy * step, iz * step)
            cache[s] = (not w.intersects(g), g.bounds[0] > 0.2)
        return cache[s]
    start = (0, 0, 0)
    if not free(start)[0]:
        return "collides when seated"
    q, seen = collections.deque([start]), {start}
    while q:
        s = q.popleft()
        if free(s)[1]:
            return True
        th, iy, iz = s
        for d in ((1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1)):
            n = (th + d[0], iy + d[1], iz + d[2])
            if abs(n[0] * dth) > 100 or abs(n[1] * step) > 30 or abs(n[2] * step) > 30 or n in seen:
                continue
            seen.add(n)
            if free(n)[0]:
                q.append(n)
    return False

def check(hook=None, lips=None, cav_back=15.5):
    """True if `hook` (param dict or history name) inserts for every lip in LIP_RANGE."""
    from .hook import HOOK, LIP_RANGE, hook_profile_pts, _params
    h = _params(hook or HOOK)
    poly = Polygon(hook_profile_pts(4.0, -10.0, h["hs"], h))
    res = {L: can_insert(poly, L, cav_top=h["ztop"] + 2, cav_back=cav_back) for L in (lips or LIP_RANGE)}
    for L, r in res.items():
        print(f"  lip {L}: {r}")
    return all(r is True for r in res.values())


if __name__ == "__main__":
    print("slathook.HOOK:", "PASS" if check() else "FAIL")
