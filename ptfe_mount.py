"""Slatwall PTFE mounts (hook geometry lives in slathook.py).

World frame (as mounted): X = along wall, Y = out of wall (wall face at Y=0), Z = up.
Slot opening spans Z = 0 .. SLOT_OPEN.

Outputs (in ./stl):
  swivel_base.stl      hooks into a slatwall slot (verified to fit ProSlat carbon fiber); bore + rear counterbore
  swivel_guide_5.stl   block with 5 full PTFE sleeves + split snap axle.
                       Hang the base, then push the axle in from the front until it clicks.
                       Rotates about the wall-normal axis so tubes can run at any angle.
  sleeve_N.stl         standalone bundling sleeve, N tubes in a row (not slatwall).
  fit_test.stl         two hook coupons (1=zL30_19 2=zF0; see slathook.HOOKS) to check fit on your panel first.
All STLs are in print orientation (no supports needed).
"""
from pathlib import Path
from build123d import *

from slathook import NECK_TOP, hooked_body, on_side, fit_test

# ---------------- PTFE ----------------
PTFE_HOLE = 4.4      # 4 mm OD tube, sliding fit (4.2 printed too tight in PETG)
PITCH = 6.6          # MMU3 grommet is 6.2; a bit wider for 2.4 mm webs
ENTRY_CHAMFER = 0.8
# ---------------- swivel base ----------------
BODY_W = 24.0
BODY_D = 14.0
# Body hangs BELOW the slot: nothing may sit above the neck top in front of the wall,
# or it hits the upper slat while you tilt the hook in.
BODY_TOP = NECK_TOP
BORE_Z = BODY_TOP - BODY_W / 2 - 6.0      # swivel axis, below the slot
BODY_Z0 = BORE_Z - BODY_W / 2
BORE_D = 8.4
CB_D = 11.4
CB_DEPTH = 4.5
BORE_CHAMFER = 1.2    # guide-in chamfer on the bore entry
# ---------------- swivel guide ----------------
GUIDE_LEN = 22.0
GUIDE_T = PTFE_HOLE + 2 * 2.2
GAP = 0.4
WASHER_D, WASHER_H = 12.0, 0.6
AXLE_D = 7.9
SLIT_W = 2.2
BARB_D = 9.3
BARB_LEN = 3.0
# ---------------- standalone sleeve ----------------
SLEEVE_LEN = 14.0    # along tube
SLEEVE_WALL = 2.2


def swivel_base() -> Part:
    p = hooked_body(BODY_W, BODY_D, BODY_Z0, BODY_TOP)
    with p:
        with Locations(Location((0, BODY_D, BORE_Z), (90, 0, 0))):
            Hole(radius=BORE_D / 2, depth=BODY_D)
        with Locations(Location((0, 0, BORE_Z), (-90, 0, 0))):
            Hole(radius=CB_D / 2, depth=CB_DEPTH)
        # lead-in chamfer on the bore entry so the axle finds the hole
        entry = [e for e in p.edges().filter_by(GeomType.CIRCLE)
                 if abs(e.center().Y - BODY_D) < 0.01 and abs(e.radius - BORE_D / 2) < 0.01]
        chamfer(entry, length=BORE_CHAMFER)
    return p.part


def swivel_guide(n=5) -> Part:
    """Built in print orientation: front face on bed (Z=0), axle up (+Z)."""
    w = (n - 1) * PITCH + PTFE_HOLE + 2 * 2.6
    w = max(w, WASHER_D + 4)
    with BuildPart() as p:
        Box(w, GUIDE_LEN, GUIDE_T, align=(Align.CENTER, Align.CENTER, Align.MIN))
        fillet(p.edges().filter_by(Axis.Z), radius=3)
        fillet(p.edges().group_by(Axis.Z)[-1], radius=1.0)      # back face (top in print)
        chamfer(p.edges().group_by(Axis.Z)[0], length=0.5)      # bed edge: chamfer, no elephant foot
        zc = GUIDE_T / 2
        r = PTFE_HOLE / 2
        for i in range(n):
            x = (i - (n - 1) / 2) * PITCH
            # round through-hole, chamfered at both ends -- same as the plain sleeves
            with Locations(Location((x, GUIDE_LEN / 2, zc), (-90, 0, 0))):
                CounterSinkHole(radius=r, counter_sink_radius=r + ENTRY_CHAMFER,
                                depth=GUIDE_LEN, counter_sink_angle=90)
            with Locations(Location((x, -GUIDE_LEN / 2, zc), (90, 0, 0))):
                CounterSinkHole(radius=r, counter_sink_radius=r + ENTRY_CHAMFER,
                                depth=0.01, counter_sink_angle=90)
        with Locations((0, 0, GUIDE_T)):
            Cylinder(WASHER_D / 2, WASHER_H, align=(Align.CENTER, Align.CENTER, Align.MIN))
        z0 = GUIDE_T + WASHER_H
        shaft_len = GAP + (BODY_D - CB_DEPTH) + 0.3
        with Locations((0, 0, z0 - 0.01)):
            Cylinder(AXLE_D / 2, shaft_len + 0.01, align=(Align.CENTER, Align.CENTER, Align.MIN))
        # small root fillet where the axle meets the washer (stress relief)
        root = [e for e in p.edges().filter_by(GeomType.CIRCLE)
                if abs(e.center().Z - z0) < 0.02 and abs(e.radius - AXLE_D / 2) < 0.01]
        fillet(root, radius=0.5)
        zb = z0 + shaft_len
        with BuildSketch(Plane.XZ):
            Polygon((0, zb), (BARB_D / 2, zb), (BARB_D / 2, zb + 0.8),
                    (AXLE_D / 2 - 0.9, zb + BARB_LEN), (0, zb + BARB_LEN), align=None)
        revolve(axis=Axis.Z)
        with Locations((0, 0, zb + BARB_LEN)):
            Box(SLIT_W, BARB_D + 2, shaft_len + BARB_LEN - 1.5,
                align=(Align.CENTER, Align.CENTER, Align.MAX), mode=Mode.SUBTRACT)
    return p.part


def sleeve(n) -> Part:
    """Standalone bundling sleeve: n tubes in a row. Built tube-axis-up (print orientation)."""
    w = (n - 1) * PITCH + PTFE_HOLE + 2 * SLEEVE_WALL
    t = PTFE_HOLE + 2 * SLEEVE_WALL
    r = PTFE_HOLE / 2
    with BuildPart() as p:
        Box(w, t, SLEEVE_LEN, align=(Align.CENTER, Align.CENTER, Align.MIN))
        fillet(p.edges().filter_by(Axis.Z), radius=t / 2 - 0.01)
        fillet(p.edges().group_by(Axis.Z)[-1], radius=0.8)
        chamfer(p.edges().group_by(Axis.Z)[0], length=0.5)
        for i in range(n):
            x = (i - (n - 1) / 2) * PITCH
            with Locations(Location((x, 0, SLEEVE_LEN), (0, 0, 0))):
                CounterSinkHole(radius=r, counter_sink_radius=r + ENTRY_CHAMFER,
                                depth=SLEEVE_LEN, counter_sink_angle=90)
            with Locations(Location((x, 0, 0), (180, 0, 0))):
                CounterSinkHole(radius=r, counter_sink_radius=r + ENTRY_CHAMFER,
                                depth=0.01, counter_sink_angle=90)
    return p.part


if __name__ == "__main__":
    out = Path(__file__).parent / "stl"
    out.mkdir(exist_ok=True)
    parts = {
        "swivel_base": on_side(swivel_base()),
        "swivel_guide_5": swivel_guide(5),
        "fit_test": fit_test(),
        **{f"sleeve_{n}": sleeve(n) for n in (2, 3, 4, 5)},
    }
    def holes_clear(part, pts, d):
        """True if a thin probe along each hole axis doesn't touch the part."""
        for x, y, z in pts:
            probe = Cylinder(0.3, 200, rotation=(90, 0, 0) if d == "Y" else (0, 0, 0)).moved(Location((x, y, z)))
            if (part & probe).volume > 1e-3:
                return False
        return True
    g = parts["swivel_guide_5"]
    assert holes_clear(g, [((i - 2) * PITCH, 0, GUIDE_T / 2) for i in range(5)], "Y"), "guide holes blocked"
    for n in (2, 3, 4, 5):
        assert holes_clear(parts[f"sleeve_{n}"], [((i - (n - 1) / 2) * PITCH, 0, 0) for i in range(n)], "Z"), f"sleeve_{n} blocked"
    def chamfers_present(part, pts, d, length):
        for x, y, z in pts:
            for sgn in (1, -1):
                if d == "Y":
                    c = Cylinder(PTFE_HOLE / 2 + 0.3, 0.2, rotation=(90, 0, 0)).moved(Location((x, sgn * (length / 2 - 0.15), z)))
                else:
                    zz = length - 0.15 if sgn > 0 else 0.15
                    c = Cylinder(PTFE_HOLE / 2 + 0.3, 0.2).moved(Location((x, y, zz)))
                if (part & c).volume > 1e-3:
                    return False
        return True
    assert chamfers_present(g, [((i - 2) * PITCH, 0, GUIDE_T / 2) for i in range(5)], "Y", GUIDE_LEN), "guide chamfers missing"
    for n in (2, 3, 4, 5):
        assert chamfers_present(parts[f"sleeve_{n}"], [((i - (n - 1) / 2) * PITCH, 0, 0) for i in range(n)], "Z", SLEEVE_LEN), f"sleeve_{n} chamfers missing"
    print("all PTFE holes go through, chamfered both ends")
    for name, part in parts.items():
        export_stl(part, str(out / f"{name}.stl"))
        bb = part.bounding_box().size
        print(f"{name:16s} valid={part.is_valid} vol={part.volume:8.1f} mm3 "
              f"size={bb.X:.1f} x {bb.Y:.1f} x {bb.Z:.1f}")
