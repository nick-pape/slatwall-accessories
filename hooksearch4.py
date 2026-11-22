import itertools
from shapely.geometry import Polygon
from tiltsim import can_insert
import slathook
LIPS = (4.3, 5.0)
base = dict(hs=8.5, ls=2.0, hb=8.0, yb=-14.5, w=5.0, roll=7.0)   # zC, the best fit
for zt, lean in itertools.product((16, 18, 20, 22, 24), (0.0, 0.1, 0.15, 0.2, 0.25)):
    h = dict(base, ztop=float(zt), lean=lean)
    slathook.HOOKS["c"] = h
    top_front = slathook.HOOKS["c"]["yb"] + lean * (zt - 7.0) + 5.0
    if top_front > -max(LIPS) - 0.3:
        print(f"top {zt} lean {lean}: riser would hit lip when seated"); continue
    poly = Polygon(slathook.hook_profile_pts(4.0, -10.0, 8.5, "c"))
    ok = all(can_insert(poly, L, cav_top=30, cav_back=15.5) is True for L in LIPS)
    print(f"top {zt} lean {lean}: {'PASS' if ok else 'fail'}  (tip forward shift {lean * (zt - 7):.1f} mm)", flush=True)
