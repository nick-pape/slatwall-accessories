from shapely.geometry import Polygon
from tiltsim import can_insert
import slathook
base = dict(slathook.HOOKS["zL30_19"])
if __name__ == "__main__":
    for ls in (1.0, 2.0, 3.0, 3.5, 4.0):
        k = f"ls{ls}"; slathook.HOOKS[k] = dict(base, ls=ls)
        poly = Polygon(slathook.hook_profile_pts(4.0, -10.0, 8.5, k))
        print(k, [can_insert(poly, L, cav_top=21, cav_back=15.5) for L in (4.3, 5.0)], flush=True)
