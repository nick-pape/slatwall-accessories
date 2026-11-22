"""Slatwall hook geometry -- shared by every accessory in this repo.

The panel maker publishes no slot drawing. These numbers come from four
Printables designs (803484 AMS bracket, 487353 spool holder, 1739130 slot nut,
1544101 mounting nut) measured on 2026-11-22; they agree closely. Refined by fit tests on a
carbon-fiber / aluminum-core panel; other panels in the same line are believed to share the channel.
Hook shape: see HOOKS (thick "Z" like the official wire hook), verified with tiltsim.py.
Run fit_test (coupons 1=zL30_19, 2=zF0) to confirm on your panel.

World frame (as mounted): X = along wall, Y = out of wall (wall face at Y=0), Z = up.
Slot opening spans Z = 0 .. SLOT_OPEN; the hook bears on the slot bottom (Z=0).

Rules for accessories:
  * Nothing in front of the wall may rise above NECK_TOP -- it would hit the upper slat
    while you tilt the hook in. Hang bodies BELOW the slot.
  * Bodies taller than ~125 mm: add a second tab at SLOT_PITCH below for anti-rotation.
"""
import math
from build123d import *

# ---------------- panel ----------------
SLOT_PITCH = 121.5   # slot-to-slot (one slot per slat, ~4.8")
SLOT_OPEN = 10.0     # vertical opening at the face (user-measured, 2026-11-22)
LIP_T = 4.3          # face lip thickness above the slot (4.0-4.5)
CAVITY_BACK = 15.0   # face -> back of cavity (official hook reaches 15)
CAVITY_UP = 15.0     # cavity reaches >= 15 above the slot bottom (official hook)
# ---------------- hook ----------------
# The panel maker's own wire hook (user-measured 2026-11-22): 2.5 mm wire; neck runs 15 mm back
# from the face, riser climbs 15 mm leaning forward, tip 6-7 mm in front of the back.
# Printed SOLID wedges of that envelope do NOT tilt in (fit test 1, 2026-11-22): the lip
# has to swing into the open triangle between neck and riser, like it does on the wire hook.
# So printed hooks are a thick "Z": short in-slot neck + thin bottom bar + upright riser.
# Shapes below are verified with tiltsim.py (2D BFS of the insertion motion) for every lip
# thickness listed in LIP_RANGE, with cavity >= 18 tall (needed for the official hook to go in).
# Fit test 2 (2026-11-22): all of z / z_short / z_thin_lip seat; z_thin_lip best => lip is
# the thin one (~4.3). Design range now 4.3-5.0 for margin.
LIP_RANGE = (4.3, 5.0)
HOOKS = {
    # hs/ls: neck height/depth inside the slot; hb: bottom-bar height behind it;
    # yb: back of riser; w: riser thickness; ztop: riser top
    "z":       dict(hs=7.0, ls=2.0, hb=4.0, yb=-14.5, w=4.0, ztop=16.0),   # works for lip 4.3-7
    "z_short": dict(hs=7.0, ls=2.0, hb=4.0, yb=-14.5, w=4.0, ztop=14.0),   # if the cavity is shorter
    "z_thin_lip": dict(hs=8.0, ls=2.0, hb=6.0, yb=-14.5, w=4.0, ztop=16.0),  # only if lip ~4.3
    # Thicker hooks for the thin lip. The big lower-back radius ("roll") is what lets a
    # thicker bar/riser corner swing through the 10 mm gap during tilt-in (tiltsim).
    "zA": dict(hs=8.5, ls=2.0, hb=7.0, yb=-14.5, w=6.0, ztop=16.0, roll=6.0),
    "zB": dict(hs=8.5, ls=2.0, hb=7.5, yb=-14.5, w=6.0, ztop=16.0, roll=7.0),
    "zC": dict(hs=8.5, ls=2.0, hb=8.0, yb=-14.5, w=5.0, ztop=16.0, roll=7.0),
    # Fit test 3 (2026-11-22): zC best; user says there's room to go higher, and asked about
    # leaning the riser forward like the official hook (barb effect vs pull-out).
    # tiltsim: height to 22 inserts (if the cavity is that tall); lean only inserts with
    # riser <= 4.5 (lean closes the open triangle the lip swings into).
    "zC20": dict(hs=8.5, ls=2.0, hb=8.0, yb=-14.5, w=5.0, ztop=20.0, roll=7.0),
    "zL15": dict(hs=8.5, ls=2.0, hb=8.0, yb=-14.5, w=4.5, ztop=20.0, roll=7.0, lean=0.15),
    "zL20": dict(hs=8.5, ls=2.0, hb=8.0, yb=-14.5, w=4.0, ztop=22.0, roll=7.0, lean=0.20),
    "zC22": dict(hs=8.5, ls=2.0, hb=8.0, yb=-14.5, w=5.0, ztop=22.0, roll=7.0),
    "zL25": dict(hs=8.5, ls=2.0, hb=8.0, yb=-14.5, w=4.0, ztop=20.0, roll=7.0, lean=0.25),
    # Fit test 4 (2026-11-22): zC20/zL15 top hits before it slides in; zC22/zL20 won't rotate
    # fully in; zL25 seats perfectly but a little tight => the upper-back of the cavity is the
    # limit and leaning the tip forward clears it. Loosened zL25 variants (all pass tiltsim):
    "zL25_19":  dict(hs=8.5, ls=2.0, hb=8.0, yb=-14.5, w=4.0, ztop=19.0, roll=7.0, lean=0.25),  # 1 mm lower
    "zL30":     dict(hs=8.5, ls=2.0, hb=8.0, yb=-14.5, w=4.0, ztop=20.0, roll=7.0, lean=0.30),  # more lean
    "zL25_b14": dict(hs=8.5, ls=2.0, hb=8.0, yb=-14.0, w=4.0, ztop=20.0, roll=7.0, lean=0.25),  # 0.5 shallower
    "zL30_19":  dict(hs=8.5, ls=2.0, hb=8.0, yb=-14.5, w=4.0, ztop=19.0, roll=7.0, lean=0.30),  # both
    # Fit test 5 (2026-11-22): zL25_19 + zL30_19 fit, zL30 + zL25_b14 too tight => the riser
    # top height is what binds; zL30_19 best. User: the 0.5 mm neck->bar step sits too close
    # to the wall face; move it 1-2 mm deeper (ls). Both pass tiltsim.
    "zF3": dict(hs=8.5, ls=3.0, hb=8.0, yb=-14.5, w=4.0, ztop=19.0, roll=7.0, lean=0.30),
    "zF4": dict(hs=8.5, ls=4.0, hb=8.0, yb=-14.5, w=4.0, ztop=19.0, roll=7.0, lean=0.30),
    # Correction: user meant the step should move TOWARD the room (smaller ls), not deeper.
    "zF1": dict(hs=8.5, ls=1.0, hb=8.0, yb=-14.5, w=4.0, ztop=19.0, roll=7.0, lean=0.30),
    # Final: no neck step at all -- one flat 8 mm bar from the face to the riser.
    "zF0": dict(hs=8.0, ls=0.0, hb=8.0, yb=-14.5, w=4.0, ztop=19.0, roll=7.0, lean=0.30),
}
HOOK = "zF0"           # default for accessories -- update once fit_test says otherwise
NECK_TOP = HOOKS[HOOK]["hs"]


def hook_profile_pts(body_d, z0, z1, hook=HOOK):
    """Closed Y-Z outline: front body (Y 0..body_d, Z z0..z1) + neck + bar + riser."""
    h = HOOKS[hook]
    hs, ls, hb, yb, w, zt = h["hs"], h["ls"], h["hb"], h["yb"], h["w"], h["ztop"]
    lean = h.get("lean", 0.0)        # forward shift of the riser per mm of height (official ~0.43)
    r = h.get("roll", 0.8)           # lower-back corner radius
    by = lambda z: yb + lean * max(0.0, z - r)   # riser back face (lean starts above the roll)
    fy = lambda z: by(z) + w                     # riser front face
    pts = [(body_d, z0), (body_d, z1), (0, z1), (0, hs), (-ls, hs), (-ls, hb),
           (fy(hb), hb), (fy(zt - 1.0), zt - 1.0), (fy(zt - 1.0) - 1.0, zt),   # chamfer, top-front
           (by(zt - 1.0) + 1.0, zt), (by(zt - 1.0), zt - 1.0)]                 # chamfer, top-back
    pts += [(yb + r - r * math.cos(a), r - r * math.sin(a))
            for a in [i * (math.pi / 2) / 12 for i in range(13)]]
    pts += [(0, 0), (0, z0)]
    return [q for i, q in enumerate(pts) if i == 0 or abs(q[0] - pts[i - 1][0]) + abs(q[1] - pts[i - 1][1]) > 1e-6]


def hooked_body(width, body_d, z0, z1=None, front_fillet=3.0, body_fillet=2.0,
                hook=HOOK) -> BuildPart:
    """Extruded hook + rectangular front body, centred on X=0. Returns the BuildPart so
    callers can keep adding/subtracting features inside `with p:`."""
    hs = HOOKS[hook]["hs"]
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


def fit_test(hooks=("zL30_19", "zF0"), width=10.0) -> Part:
    """One small coupon per hook style, numbered 1..n on the front face."""
    coupons = []
    for k, hk in enumerate(hooks):
        body = hooked_body(width, 4.0, -10.0, None, front_fillet=0, body_fillet=0, hook=hk).part
        face_plane = Plane(origin=(0, 4.0, -4.5), x_dir=(1, 0, 0), z_dir=(0, 1, 0))
        label = extrude(face_plane * Text(str(k + 1), font_size=7), amount=-0.6)
        q = on_side(body - label)
        coupons.append(q.translate((0, k * 30.0, 0)))
    return Compound(children=coupons)
