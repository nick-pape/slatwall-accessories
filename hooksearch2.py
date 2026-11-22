import itertools, sys
from shapely.geometry import Polygon
from tiltsim import can_insert

def zhook2(hb, hs, ls, w, s, ztop, yb=-14.5, body_d=4.0, z0=-10.0):
    """hb: bar height behind the neck; hs: neck height in the slot (Y from 0 to -ls)."""
    front = lambda z: yb + w + s * z
    pts = [(body_d, z0), (body_d, hs), (-ls, hs), (-ls, hb), (front(hb), hb), (front(ztop), ztop),
           (yb + s * ztop, ztop), (yb, 0), (0, 0), (0, z0)]
    return Polygon(pts)

if __name__ == "__main__":
    LIPS = [float(x) for x in sys.argv[1:]]
    for hb, hs, ls, w, s, ztop in itertools.product((4, 5, 6), (5, 6, 7, 8), (2.0, 4.0), (4, 5), (0.0, 0.1), (14, 16)):
        if hs < hb or any(-14.5 + w + s * ztop > -L - 0.3 for L in LIPS):
            continue
        if all(can_insert(zhook2(hb, hs, ls, w, s, ztop), L, cav_top=18) is True for L in LIPS):
            print("PASS bar", hb, "slot-neck", hs, "x", ls, "riser w", w, "lean", s, "top", ztop, flush=True)
