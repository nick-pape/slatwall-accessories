from shapely.geometry import Polygon
from tiltsim import can_insert
import slathook
base = dict(hs=8.5, ls=2.0, hb=8.0, yb=-14.5, roll=7.0)
V = {"zL25": dict(w=4.0, ztop=20.0, lean=0.25),
     "zL25_19": dict(w=4.0, ztop=19.0, lean=0.25),
     "zL30": dict(w=4.0, ztop=20.0, lean=0.30),
     "zL25_t36": dict(w=3.6, ztop=20.0, lean=0.25),
     "zL25_b14": dict(w=4.0, ztop=20.0, lean=0.25, yb=-14.0),
     "zL30_19": dict(w=4.0, ztop=19.0, lean=0.30)}
if __name__ == "__main__":
    for k, v in V.items():
        slathook.HOOKS[k] = dict(base, **v)
        poly = Polygon(slathook.hook_profile_pts(4.0, -10.0, 8.5, k))
        r = [can_insert(poly, L, cav_top=v["ztop"] + 2, cav_back=15.5) for L in (4.3, 5.0)]
        print(k, r, flush=True)
