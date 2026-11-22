"""Every hook shape tried on the way to slathook.hook.HOOK, with the fit-test notes.

Kept so old designs can be rebuilt and so new hook experiments start from what is known.
Use a name anywhere a hook is accepted, e.g. hooked_body(..., hook="zC").
Coordinates as in slathook.hook. Every entry passes slathook.tiltsim for LIP_RANGE unless noted.
"""
# The panel maker's own wire hook (measured 2026-11-22): 2.5 mm wire; neck runs 15 mm back
# from the face, riser climbs 15 mm leaning forward, tip 6-7 mm in front of the back.
# Printed SOLID wedges of that envelope do NOT tilt in (fit test 1, 2026-11-22): the lip
# has to swing into the open triangle between neck and riser, like it does on the wire hook.
# So printed hooks are a thick "Z": short in-slot neck + thin bottom bar + upright riser.
# Shapes below are verified with tiltsim.py (2D BFS of the insertion motion) for every lip
# thickness listed in LIP_RANGE, with cavity >= 18 tall (needed for the official hook to go in).
# Fit test 2 (2026-11-22): all of z / z_short / z_thin_lip seat; z_thin_lip best => lip is
# the thin one (~4.3). Design range now 4.3-5.0 for margin.
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
    # Fit test 3 (2026-11-22): zC best; there is room to go higher; also tried
    # leaning the riser forward like the maker's wire hook (barb effect vs pull-out).
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
    # top height is what binds; zL30_19 best. Next question: the 0.5 mm neck->bar step sits too close
    # to the wall face; move it 1-2 mm deeper (ls). Both pass tiltsim.
    "zF3": dict(hs=8.5, ls=3.0, hb=8.0, yb=-14.5, w=4.0, ztop=19.0, roll=7.0, lean=0.30),
    "zF4": dict(hs=8.5, ls=4.0, hb=8.0, yb=-14.5, w=4.0, ztop=19.0, roll=7.0, lean=0.30),
    # Fit test 6 feedback: the step should move TOWARD the room (smaller ls), not deeper.
    "zF1": dict(hs=8.5, ls=1.0, hb=8.0, yb=-14.5, w=4.0, ztop=19.0, roll=7.0, lean=0.30),
    # Final: no neck step at all -- one flat 8 mm bar from the face to the riser.
    "zF0": dict(hs=8.0, ls=0.0, hb=8.0, yb=-14.5, w=4.0, ztop=19.0, roll=7.0, lean=0.30),
}
