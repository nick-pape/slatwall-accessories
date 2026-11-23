"""Pure-Python hook profile + panel dimensions (no CAD kernel): importable anywhere, incl. Pyodide.
See slathook.hook for the shape rationale and the build123d solids."""
import math

SLOT_PITCH = 120.65  # slot-to-slot, user-measured top-to-top 4 3/4" (2026-11-22); research said ~121.5
SLOT_OPEN = 10.0     # vertical opening at the face
LIP_T = 4.3          # face lip thickness above the slot
LIP_RANGE = (4.3, 5.0)  # lip thicknesses every hook must insert with (tiltsim)

# ---------------- the hook (final, fit-test #6) ----------------
HOOK = dict(
    hs=8.0,      # bar height in the slot (= NECK_TOP)
    ls=0.0,      # length of an optional taller neck section at the face (0 = none)
    hb=8.0,      # bar height behind the face
    yb=-14.5,    # back face of the riser, measured from the wall face
    w=4.0,       # riser thickness
    ztop=19.0,   # riser top above the slot bottom (20 binds on the cavity's upper back)
    roll=7.0,    # lower-back corner radius (lets the corner swing through the slot)
    lean=0.30,   # riser leans forward 0.30 mm per mm of height (tip ~3.6 mm forward)
)
NECK_TOP = HOOK["hs"]


def _params(hook):
    if isinstance(hook, str):
        from .history import HOOKS
        return HOOKS[hook]
    return hook


def hook_profile_pts(body_d, z0, z1, hook=HOOK):
    """Closed Y-Z outline: front body (Y 0..body_d, Z z0..z1) + bar + riser.
    body_d=0 and z0=0 gives the bare hook (attach face on Y=0, Z 0..NECK_TOP)."""
    h = _params(hook)
    hs, ls, hb, yb, w, zt = h["hs"], h["ls"], h["hb"], h["yb"], h["w"], h["ztop"]
    lean = h.get("lean", 0.0)
    r = h.get("roll", 0.8)
    by = lambda z: yb + lean * max(0.0, z - r)   # riser back face (lean starts above the roll)
    fy = lambda z: by(z) + w                     # riser front face
    pts = [(body_d, z0), (body_d, z1), (0, z1), (0, hs), (-ls, hs), (-ls, hb),
           (fy(hb), hb), (fy(zt - 1.0), zt - 1.0), (fy(zt - 1.0) - 1.0, zt),   # chamfer, top-front
           (by(zt - 1.0) + 1.0, zt), (by(zt - 1.0), zt - 1.0)]                 # chamfer, top-back
    pts += [(yb + r - r * math.cos(a), r - r * math.sin(a))
            for a in [i * (math.pi / 2) / 12 for i in range(13)]]
    pts += [(0, 0), (0, z0)]
    return [q for i, q in enumerate(pts) if i == 0 or abs(q[0] - pts[i - 1][0]) + abs(q[1] - pts[i - 1][1]) > 1e-6]
