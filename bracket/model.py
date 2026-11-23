"""The bracket problem: design space, fixed regions, wall contact and load cases.

Everything in front of the wall (x >= 0) below the bar top (z <= NECK_TOP) is design space.
Behind the face only the slatwall hook (fixed shape, from slathook) exists. The deck sits on a
fixed top flange. Wall contact is unilateral:
  * hook bar bottom on the slot floor       (can push up, never pull down)
  * riser front on the back of the face lip  (can push the hook back into the wall)
  * bracket back face on the wall face       (can push, never pull), except across slots
"""
import math, sys
from pathlib import Path
import numpy as np
from shapely.geometry import Polygon
from shapely import contains_xy

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from slathook import HOOK, NECK_TOP, SLOT_PITCH, SLOT_OPEN, hook_profile_pts
from fea import Grid, Contact

REST_TAB = (4.0, 7.0)   # rest tab: depth into the lower slot, height (slot is 10 open)
E_PETG = 1600.0      # MPa, Prusament PETG datasheet tensile modulus 1.5-1.6 GPa (was 2.0 in the sizing runs)
NU = 0.38


class Bracket:
    def __init__(self, depth=200.0, z_bottom=-130.0, h=1.0, t=12.0, flange=3.0, lip_gap=0.0, rest=False):
        self.depth, self.t, self.h = depth, t, h
        # snap the grid so nodes land exactly on x=0 (wall face) and z=NECK_TOP (deck)
        x0 = -math.ceil(16.0 / h) * h
        self.top = NECK_TOP
        z_bottom = NECK_TOP - math.ceil((NECK_TOP - z_bottom) / h) * h
        z_top = NECK_TOP + math.ceil((HOOK["ztop"] + 1.0 - NECK_TOP) / h) * h
        nx = int(round((math.ceil(depth / h) * h - x0) / h))
        nz = int(round((z_top - z_bottom) / h))
        g = self.grid = Grid(x0, z_bottom, nx, nz, h)
        hook = Polygon(hook_profile_pts(0.0, 0.0, NECK_TOP, HOOK))
        self.hook_poly = hook
        in_hook = contains_xy(hook, g.xc, g.zc)
        front = (g.xc > 0) & (g.zc < self.top)
        # optional rest tab: sits in the NEXT slot down and bears on its floor (no hook)
        self.rest = rest
        self.rest_floor = REST_FLOOR = NECK_TOP - math.ceil((NECK_TOP + SLOT_PITCH) / h) * h   # ~ -121.5, on a grid line
        in_tab = rest & (g.xc > -REST_TAB[0]) & (g.xc < 0) & (g.zc > REST_FLOOR) & (g.zc < REST_FLOOR + REST_TAB[1])
        self.solid = in_hook | in_tab | (front & (g.zc > self.top - flange))  # fixed solid
        self.design = front & ~self.solid
        self.void = ~(self.solid | self.design)                               # fixed void
        # ---- contact supports ----
        xn, zn = g.xn, g.zn
        tol = h / 2
        # nodes that touch solid-or-design elements (so contact nodes are part of the body)
        floor = np.where(np.isclose(zn, 0, atol=1e-6) & (xn > HOOK["yb"] + HOOK["roll"] - tol) & (xn <= 0 + 1e-6))[0]
        # riser front face: nodes on the hook boundary, top 3 mm of the riser, front side
        rz = (zn > HOOK["ztop"] - 4) & (zn < HOOK["ztop"] - 1 + 1e-6)
        cand = np.where(rz & (xn < 0) & contains_xy(hook.buffer(1e-6), xn, zn))[0]
        riser = []
        for zz in np.unique(zn[cand]):                                       # frontmost node per row
            row = cand[np.isclose(zn[cand], zz)]
            riser.append(row[np.argmax(xn[row])])
        riser = np.array(riser)
        slots = [(-k * SLOT_PITCH, -k * SLOT_PITCH + SLOT_OPEN) for k in range(0, 3)]
        wall = np.where(np.isclose(xn, 0, atol=1e-6) & (zn < 0 - 1e-6) & (zn > z_bottom - 1e-6))[0]
        wall = wall[[not any(a - 1e-6 <= z <= b + 1e-6 for a, b in slots) for z in zn[wall]]]
        self.support_nodes = dict(floor=floor, riser=riser, wall=wall)
        tabfloor = np.where(rest & np.isclose(zn, self.rest_floor, atol=1e-6) & (xn >= -REST_TAB[0] - 1e-6) & (xn <= 1e-6))[0]
        self.support_nodes["rest"] = tabfloor
        self.groups = [(2 * floor + 1, +1),      # floor pushes up
                       (2 * tabfloor + 1, +1),   # lower slot floor carries the rest tab (push up only)
                       (2 * riser, -1),          # lip back stops the riser moving out (+x)
                       (2 * wall, +1)]           # wall face stops the body moving in (-x)

    def contact(self, kpen):
        return Contact(self.groups, kpen)

    def loads(self, total=1.0):
        """Two load cases (columns): uniform deck load, and the whole load at the front edge."""
        g = self.grid
        top = np.where(np.isclose(g.zn, self.top, atol=1e-6) & (g.xn >= 0) & (g.xn <= self.depth + 1e-6))[0]
        F = np.zeros((2 * g.nnode, 2))
        F[2 * top + 1, 0] = -total / len(top)
        tip = top[g.xn[top] >= self.depth - 5.0]
        F[2 * tip + 1, 1] = -total / len(tip)
        return F
