"""The slatwall hook -- the one profile every accessory in this repo hangs from.

Verified to fit ProSlat carbon fiber slatwall (six printed fit tests, PETG, 2026-11-22).
The panel maker publishes no slot drawing; dimensions are measured.

World frame (as mounted): X = along the wall, Y = out of the wall (wall face at Y=0),
Z = up. The slot opening spans Z = 0 .. SLOT_OPEN; the hook bears on the slot bottom (Z=0).

Shape: a thick "Z" seen from the side --
  * a flat bar, BAR_H tall, runs from the wall face back through the 10 mm slot,
  * a riser climbs behind the face lip, leaning forward like the maker's own wire hook,
  * a big radius on the lower-back corner lets the part rock in through the slot.

Rules for accessories:
  * Nothing in front of the wall may rise above NECK_TOP -- it hits the slat above while
    you tilt the part in. Hang bodies BELOW the slot.
  * Solid wedge-shaped hooks don't go in: the lip must swing into the open space between
    the bar and the riser. Check any new shape with slathook.tiltsim first.
  * Bodies taller than ~125 mm: add a second hook at SLOT_PITCH below for anti-rotation.

Quick use:
    from slathook import hooked_body, hook_part, on_side, NECK_TOP
    p = hooked_body(width=24, body_d=14, z0=-20)      # hook + block, keep modelling in `with p:`
    part = my_body + hook_part(width=20)             # or union the bare hook onto any body
"""
import math
from build123d import *

# ---------------- panel (measured) ----------------
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


def hook_face(hook=HOOK, overlap=0.5) -> Face:
    """The bare hook profile as a Face in the Y-Z plane. `overlap` extends it into +Y so a
    union with your body (front face at Y=0) fuses cleanly."""
    pts = hook_profile_pts(overlap, 0.0, _params(hook)["hs"], hook)
    return Face(Wire.make_polygon([Vector(0, y, z) for y, z in pts], close=True))


def hook_part(width, hook=HOOK, overlap=0.5) -> Part:
    """Bare hook, `width` wide along X and centred on X=0. Union it onto any body whose
    back face sits on Y=0 and spans Z 0..NECK_TOP."""
    p = extrude(hook_face(hook, overlap).moved(Location((-width / 2, 0, 0))), amount=width, dir=(1, 0, 0))
    he = [e for e in p.edges() if e.center().Y < -0.3 and e.geom_type == GeomType.LINE
          and abs(e.tangent_at(0).X) < 0.01]
    return fillet(he, radius=0.4)


def hooked_body(width, body_d, z0, z1=None, front_fillet=3.0, body_fillet=2.0,
                hook=HOOK) -> BuildPart:
    """Hook + rectangular front body (Y 0..body_d, Z z0..z1), centred on X=0. Returns the
    BuildPart so callers can keep adding/subtracting features inside `with p:`."""
    hs = _params(hook)["hs"]
    z1 = hs if z1 is None else z1
    assert z1 <= hs + 1e-6, "front body must not rise above the neck (blocks tilt-in)"
    p = BuildPart()
    with p:
        with BuildSketch(Plane.YZ.offset(-width / 2)):
            Polygon(*hook_profile_pts(body_d, z0, z1, hook), align=None)
        extrude(amount=width)
        if front_fillet:
            fe = p.edges().filter_by(Axis.Z).filter_by(lambda e: e.center().Y > body_d - 0.1)
            fillet(fe, radius=front_fillet)
        if body_fillet:
            be = [e for e in p.edges() if e.center().Y > 0.3 and e.bounding_box().min.Y > -0.01
                  and not (e.geom_type == GeomType.LINE and abs(e.tangent_at(0).Z) > 0.99
                           and e.center().Y > body_d - 0.1)]
            for r in (body_fillet, 0.75 * body_fillet, 0.5 * body_fillet):
                try:            # OCC occasionally rejects the full radius on some hook shapes
                    fillet(be, radius=r)
                    break
                except ValueError:
                    continue
        # soften the hook's side edges a little
        he = [e for e in p.edges() if e.center().Y < -0.3 and e.geom_type == GeomType.LINE
              and abs(e.tangent_at(0).X) < 0.01 and abs(abs(e.center().X) - width / 2) < 0.01]
        fillet(he, radius=0.4)
    return p


def on_side(part: Part) -> Part:
    """Print orientation for hooked parts: hook profile flat on the bed (X axis up)."""
    q = part.rotate(Axis.Y, 90)
    return q.translate((0, 0, -q.bounding_box().min.Z))


def fit_test(hooks=(HOOK,), width=10.0) -> Part:
    """Small coupon(s) to check the hook on your panel, numbered 1..n on the front face.
    `hooks` takes param dicts or names from slathook.history.HOOKS."""
    coupons = []
    for k, hk in enumerate(hooks):
        body = hooked_body(width, 4.0, -10.0, None, front_fillet=0, body_fillet=0, hook=hk).part
        face_plane = Plane(origin=(0, 4.0, -4.5), x_dir=(1, 0, 0), z_dir=(0, 1, 0))
        label = extrude(face_plane * Text(str(k + 1), font_size=7), amount=-0.6)
        q = on_side(body - label)
        coupons.append(q.translate((0, k * 30.0, 0)))
    return coupons[0] if len(coupons) == 1 else Compound(children=coupons)
