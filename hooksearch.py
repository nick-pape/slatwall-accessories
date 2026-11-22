import itertools, time, sys
from shapely.geometry import Polygon
from tiltsim import can_insert

def zhook(hn, w, s, ztop, yb=-14.5, body_d=4.0, z0=-10.0):
    """Thick wire-style hook: bottom bar (height hn) + forward-leaning riser (horizontal width w)."""
    front = lambda z: yb + w + s * z      # riser front face
    back = lambda z: yb + s * z           # riser back face
    pts = [(body_d, z0), (body_d, hn), (front(hn), hn), (front(ztop), ztop),
           (back(ztop), ztop), (yb, 0), (0, 0), (0, z0)]
    return Polygon(pts)

def ok_seated(hn, w, s, ztop, lip, yb=-14.5):
    # riser front (most forward at its top) must stay behind the lip
    return yb + w + s * ztop <= -lip - 0.3 and hn <= 9.6

if __name__ == "__main__":
    LIPS = [float(x) for x in sys.argv[1:]] or [4.3, 6.5, 7.0]
    res = []
    t0 = time.time()
    for hn, w, s, ztop in itertools.product((4, 5, 6, 7, 8), (3.5, 4, 5), (0.0, 0.1, 0.2, 0.3), (12, 14, 16)):
        if not all(ok_seated(hn, w, s, ztop, L) for L in LIPS):
            continue
        p = zhook(hn, w, s, ztop)
        r = [can_insert(p, L, cav_top=18) is True for L in LIPS]
        if all(r):
            res.append((hn, w, s, ztop))
            print("PASS", hn, w, s, ztop, flush=True)
    print("done in", round(time.time() - t0), "s;", len(res), "passing")
