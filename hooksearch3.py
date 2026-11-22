import itertools
from shapely.geometry import Polygon
from tiltsim import can_insert
import slathook

LIPS = (4.3, 5.0)
rows = []
for hb, w, hs, yb in itertools.product((6, 7, 8, 9), (4, 5, 6, 7, 8), (8.0, 8.5, 9.0), (-14.5, -15.0)):
    if hs < hb or yb + w > -max(LIPS) - 0.3:
        continue
    slathook.HOOKS["cand"] = dict(hs=hs, ls=2.0, hb=hb, yb=yb, w=w, ztop=16.0)
    poly = Polygon(slathook.hook_profile_pts(4.0, -10.0, hs, "cand"))
    if all(can_insert(poly, L, cav_top=18) is True for L in LIPS):
        rows.append((hb, w, hs, yb))
        print("PASS bar", hb, "riser", w, "neck", hs, "back", yb, flush=True)
