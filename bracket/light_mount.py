"""Shop-light mount: slatwall base + carbon-fibre tube arm + drop-in cradle, for a 4 ft D-profile LED shop light.

  BASE    hook in a slot, a twin-wall ladder pad down the wall face (no rest tab -- the light weighs
          ~0.4 kg on two mounts), and a socket that holds an 18 mm OD carbon-fibre tube at `angle`.
  TUBE    16 x 18 x 500 mm CF tube (uncut by default) -- the reach a printed arm can't have on a Mk4.
  CRADLE  slips onto the tube's top end. Curtain-rod style: the light is lowered into an open sling,
          flat (warm, LED) side up. The sling keeps an air gap off the diffuser and touches it only on
          a few thin ribs. Separate part so it can be iterated without reprinting the base.

Both printed parts are profiles extruded along the wall and print standing (profile on the bed), modelled
as signed distance fields (sdfpart.py): everything after the hook is rounded to match the tube and the
light, every joint is filleted, bottom edges are 45 deg teardrops, and the tube bores are teardrops
(apex up) with crush ribs.

    uv run python light_mount.py [--tube 500] [--angle 45] [--aim 0] [--gap 3] [--open]
Light profile: W wide (flat side) x H tall (flat top + curved diffuser), default 3" x 1.5".
"""
import argparse, math, subprocess, sys, re, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union
from shapely import affinity


from catalog import TOP, HOOKP

HERE = Path(__file__).parent
OUT = HERE / "out" / "print"
WIDTH = 28.0           # both parts' width along the wall (= print height)
TUBE_OD = 18.0
BORE = TUBE_OD + 0.4   # bore diameter; crush ribs take it back to OD - 0.3
RIB_IN = 0.35          # crush rib height
SLEEVE_T = 4.0         # wall around the bore (in the profile plane)
ENGAGE = 40.0          # tube insertion depth into each socket
CAP = 5.0              # closed end of each socket


def _band(p, q, half, ext=0.0):
    u = (q - p) / np.linalg.norm(q - p)
    return LineString([p - u * ext, q + u * ext]).buffer(half, cap_style=2)


def _capsule(p, q, r):
    return LineString([p, q]).buffer(r, quad_segs=16)


def _fillet(g, R):
    """Round concave corners with radius R (morphological closing)."""
    return g.buffer(R, quad_segs=16).buffer(-R, quad_segs=16)


def base_profile(angle=45.0, pad=60.0, clear=6.0, drop=15.0, spine_r=7.0, brace_r=5.0, brace_at=0.75):
    """Base: hook + root, a round spine down the wall face, a round brace from the spine's foot to the
    socket's underside, and the round tube socket. Returns (2D outline, SDF spec, mouth, bore bottom, axis)."""
    from sdfpart import d_capsule, d_halfplane, d_poly
    a = math.radians(angle)
    u = np.array([math.cos(a), math.sin(a)]); n = np.array([-u[1], u[0]])
    hs = BORE / 2 + SLEEVE_T                                  # socket radius
    S0 = np.array([clear, TOP - drop]) - n * hs              # socket bottom end: upper-left edge at (clear, TOP - drop)
    S1 = S0 + u * (ENGAGE + CAP)                             # mouth
    foot = np.array([spine_r, TOP - pad + spine_r])
    top = np.array([spine_r, TOP - 4])
    Pd = S0 + u * (ENGAGE + CAP) * brace_at - n * (hs - brace_r)
    root = box(0, TOP - 14, 9, TOP)
    hook = unary_union([HOOKP, box(0, 0, 2, TOP)])
    above = box(-60, TOP, 1e3, TOP + 200).difference(_band(S0, S1, hs).buffer(0.6))   # tilt-in: nothing up here but the socket
    spec = dict(
        members=[(lambda X, Z: np.maximum(d_capsule(X, Z, S0, S1, hs), d_halfplane(X, Z, S1, u)), hs),
                 (lambda X, Z: d_capsule(X, Z, top, foot, spine_r), spine_r),
                 (lambda X, Z: d_capsule(X, Z, foot, Pd, brace_r), brace_r),
                 (lambda X, Z: d_poly(X, Z, root), 2.0)],
        cut2d=[lambda X, Z: X, lambda X, Z: d_poly(X, Z, above)],
        add=[(lambda X, Z: d_poly(X, Z, hook), 0.8)], k=6.0)
    outline = unary_union([_band(S0, S1, hs), Point(S0).buffer(hs), LineString([top, foot]).buffer(spine_r),
                           LineString([foot, Pd]).buffer(brace_r), root]).intersection(box(0, -1e3, 1e3, 1e3)).union(hook)
    spec["bounds"] = outline.bounds
    return outline, spec, S1, S0 + u * CAP, u


CAP_W, CAP_H, CAP_L = 72.9, 32.0, 40.0      # end cap: 2.87" x 1.26" (listing); length along the light is a guess
TUBE_R = 15.5                                 # the two LED tubes between the caps (warm -- never touched)


def light_outline(W=CAP_W, H=CAP_H, r=10.0):
    """End-cap cross-section: W wide x H tall, top at z=0. The cradle holds the CAPS, not the tubes."""
    return box(-W / 2, -H, W / 2, 0).buffer(-r, join_style=1).buffer(r, join_style=1)


def cradle_profile(E, u, W=CAP_W, H=CAP_H, aim=0.0, gap=1.0, t=3.0, wall_up=0.6, rib=0.7):
    """Open-top tray on the tube end E (axis u) that an end cap drops into. Ends are open (the link
    socket and cord come out of the cap's end face). Thin ribs touch the cap; `gap` everywhere else.
    `aim` tilts the light toward the bench (0 = straight down). Returns (geom, cap outline, bore start, bore end)."""
    hs = BORE / 2 + SLEEVE_T
    B0, B1 = E - u * ENGAGE, E + u * CAP
    sleeve = _band(B0, B1, hs)
    zt = -H + wall_up * H                               # wall tops
    capo = light_outline(W, H)
    tray = capo.buffer(gap + t, quad_segs=16).difference(capo.buffer(gap, quad_segs=16)).intersection(box(-1e3, -1e3, 1e3, zt))
    tray = tray.buffer(-0.6, join_style=1).buffer(0.6, join_style=1)                 # round the wall tops
    shell = capo.buffer(gap + 0.2).difference(capo.buffer(0.3))                       # rib zone: 0.3 mm short of the cap
    strips = [box(x - 1.0, -H - 5, x + 1.0, -H + 5) for x in (-W / 3, 0, W / 3)]        # floor contacts
    strips += [box(-W, -H * 0.55 - 1, W, -H * 0.55 + 1)]                               # side contacts at mid-height
    ribs = [shell.intersection(unary_union(strips))]
    cr = unary_union([tray, *ribs])
    cap = light_outline(W, H)
    cr, cap = (affinity.rotate(g, aim, origin=(0, 0)) for g in (cr, cap))
    # sit the tray centred over the tube end, its floor overlapping the sleeve's top corner
    cx = (cr.bounds[0] + cr.bounds[2]) / 2
    dx, dz = E[0] - cx, sleeve.bounds[3] - 2.0 - cr.bounds[1]
    cr, cap = (affinity.translate(g, dx, dz) for g in (cr, cap))
    above = np.array([E[0], cr.bounds[1] + t / 2])
    from sdfpart import d_capsule, d_halfplane, d_poly
    tray = unary_union([tray_only for tray_only in [affinity.translate(affinity.rotate(tray, aim, origin=(0, 0)), dx, dz)]])
    rib = affinity.translate(affinity.rotate(unary_union(ribs), aim, origin=(0, 0)), dx, dz)
    clear = cap.buffer(gap, quad_segs=32)
    rp = hs * 0.7
    spec = dict(
        members=[(lambda X, Z: np.maximum(d_capsule(X, Z, B0, B1, hs), d_halfplane(X, Z, B0, -u)), hs),
                 (lambda X, Z: d_capsule(X, Z, E, above, rp), rp),
                 (lambda X, Z: d_poly(X, Z, tray), t / 2 - 0.1)],
        cut2d=[lambda X, Z: d_poly(X, Z, clear)],
        add=[(lambda X, Z: d_poly(X, Z, rib), 0.3)], k=7.0)
    geom = unary_union([_band(B0, B1, hs), Point(B1).buffer(hs), LineString([E, above]).buffer(rp), tray, rib])
    spec["bounds"] = geom.bounds
    return geom, cap, B0, E, spec


def build(tube=500.0, angle=45.0, aim=0.0, gap=1.0, W=CAP_W, H=CAP_H):
    base, bspec, mouth, b0, u = base_profile(angle)
    E = b0 + u * tube                                        # tube top end (b0 = bottom of the base bore)
    cradle, light, c0, c1, cspec = cradle_profile(E, u, W, H, aim, gap)
    tube_poly = _band(b0, E, TUBE_OD / 2)
    return dict(base=base, base_spec=bspec, cradle_spec=cspec, cradle=cradle, light=light, tube=tube_poly, base_bore=(mouth, b0),
                cradle_bore=(c0, c1), u=u, E=E)


def meshes(m, res=0.2):
    from sdfpart import build
    return tuple(build(h=WIDTH, res=res, bores=[m[f"{p}_bore"]], bore_R=BORE / 2, **m[f"{p}_spec"]) for p in ("base", "cradle"))


def check_insert(prof):
    import slathook.tiltsim as ts
    return {lip: ts.can_insert(prof.simplify(0.3), lip, step=0.5, dth=1.0, cav_top=21.0) for lip in (4.3, 5.0)}


def preview(m, path):
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import PathPatch
    from matplotlib.path import Path as MPath
    from slathook import SLOT_OPEN, SLOT_PITCH

    def patch(g, **kw):
        for p in getattr(g, "geoms", [g]):
            verts, codes = [], []
            for ring in [p.exterior, *p.interiors]:
                c = list(ring.coords); verts += c; codes += [MPath.MOVETO] + [MPath.LINETO] * (len(c) - 2) + [MPath.CLOSEPOLY]
            ax.add_patch(PathPatch(MPath(verts, codes), **kw))
    fig, ax = plt.subplots(figsize=(8, 8))
    wallp = unary_union([box(-20, -SLOT_PITCH + SLOT_OPEN, 0, 0), box(-20, SLOT_OPEN, 0, SLOT_PITCH)])
    patch(wallp, fc="#ccc", ec="none")
    patch(m["tube"], fc="#333", ec="none", alpha=0.85)
    patch(m["light"], fc="#fff6c8", ec="#b59a2a", lw=1)
    patch(m["base"], fc="#3a6ea5", ec="none")
    patch(m["cradle"], fc="#d9822b", ec="none")
    ax.set_aspect("equal"); ax.autoscale(); ax.margins(0.05)
    ax.set_xlabel("mm out from wall"); ax.set_ylabel("mm above the slot")
    ax.set_title("light mount: base (blue), CF tube, cradle (orange), light outline"); ax.grid(alpha=0.2)
    fig.savefig(path, dpi=120, bbox_inches="tight"); plt.close(fig)



def assembly(m, base_mesh, cradle_mesh, path, light_len=1194.0):
    """Everything in place (view-only 3MF): wall section, 2 bases, 2 tubes, 2 cradles, the light.
    World: x out of the wall, y along the wall, z up."""
    import trimesh
    from slathook import SLOT_OPEN, SLOT_PITCH

    def prism(poly, y0, h):                 # profile (x, z) extruded along y from y0
        ms = [trimesh.creation.extrude_polygon(p, h) for p in getattr(poly, "geoms", [poly]) if p.area > 1]
        mm = trimesh.util.concatenate(ms)
        mm.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, [1, 0, 0]))   # (x,y,z)->(x,-z,y)
        mm.apply_translation([0, y0 + h, 0])
        return mm
    ys = [CAP_L / 2 - WIDTH / 2, light_len - CAP_L / 2 - WIDTH / 2]          # one cradle under each end cap
    wall = unary_union([box(-20, -SLOT_PITCH * 1.5, 0, -SLOT_PITCH), box(-20, -SLOT_PITCH + SLOT_OPEN, 0, 0),
                        box(-20, SLOT_OPEN, 0, SLOT_PITCH * 0.9)])
    parts = {"slatwall": prism(wall, -100, light_len + 200), "end cap 1": prism(m["light"], 0, CAP_L),
             "end cap 2": prism(m["light"], light_len - CAP_L, CAP_L)}
    c = m["light"].centroid; cb = m["light"].bounds
    for k, sx in (("LED tube 1", -1), ("LED tube 2", 1)):
        tube = Point(c.x + sx * (cb[2] - cb[0]) / 4, c.y - 1).buffer(TUBE_R).intersection(box(-1e3, cb[1] + 1, 1e3, cb[3] - 4))
        parts[k] = prism(tube, CAP_L, light_len - 2 * CAP_L)
    b0, E, u = m["base_bore"][1], m["E"], m["u"]
    L = np.linalg.norm(E - b0)
    for i, y in enumerate(ys):
        T = np.array([[1, 0, 0, 0], [0, 0, 1, y], [0, 1, 0, 0], [0, 0, 0, 1.0]])     # print (X, Y, Z) -> world (x, y, z)
        parts[f"base {i + 1}"] = base_mesh.copy().apply_transform(T)
        parts[f"cradle {i + 1}"] = cradle_mesh.copy().apply_transform(T)
        t = trimesh.creation.annulus(r_min=8.0, r_max=TUBE_OD / 2, height=L, sections=48)
        d = np.array([u[0], 0, u[1]])
        t.apply_transform(trimesh.geometry.align_vectors([0, 0, 1], d))
        mid = (b0 + E) / 2
        t.apply_translation([mid[0], y + WIDTH / 2, mid[1]])
        parts[f"CF tube {i + 1}"] = t
    from infill_shelf import write_3mf       # one object, one named part per piece (keeps the layout)
    write_3mf(path, [(k, v, "ModelPart", {}) for k, v in parts.items()], {}, "light mount assembly (view only)")
    return path


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tube", type=float, default=500.0, help="CF tube length (mm)")
    ap.add_argument("--angle", type=float, default=45.0, help="arm angle above horizontal")
    ap.add_argument("--aim", type=float, default=-15.0, help="light tilt from straight down, deg: negative = toward the wall (default -15 balances wall + bench)")
    ap.add_argument("--gap", type=float, default=1.0, help="clearance between tray and end cap (mm); ribs touch")
    ap.add_argument("--W", type=float, default=CAP_W); ap.add_argument("--H", type=float, default=CAP_H)
    ap.add_argument("--open", action="store_true")
    a = ap.parse_args()
    m = build(a.tube, a.angle, a.aim, a.gap, a.W, a.H)
    preview(m, OUT / "light_mount_preview.png")
    E = m["E"]
    print(f"tube end {E[0]:.0f} mm out, {E[1]:.0f} mm up; light centre ~{m['light'].centroid.x:.0f} out, {m['light'].centroid.y:.0f} up")
    print("tilt-in:", check_insert(m["base"]))
    base, cradle = meshes(m)
    for nm, p in (("light_base", base), ("light_cradle", cradle)):
        print(f"{nm}: watertight {p.is_watertight}, {p.extents.round(0)} mm, {p.volume * 1.27e-3:.1f} g solid")
        p.export(str(OUT / f"{nm}.stl"))
    asm = assembly(m, base, cradle, OUT / "light_mount_assembly.3mf")
    print("assembly:", asm)
    tmf = OUT / "light_mount.3mf"
    subprocess.run([sys.executable, str(HERE.parent / "tools/make_3mf.py"), str(tmf), str(HERE.parent / "tools/prusa/cfg_extruded.ini"),
                    f"{OUT / 'light_base.stl'}:2", f"{OUT / 'light_cradle.stl'}:2"], check=True)
    PS = r"C:\Program Files\Prusa3D\PrusaSlicer\prusa-slicer-console.exe"
    (OUT / "tmp.gcode").unlink(missing_ok=True)
    r = subprocess.run([PS, "--binary-gcode=0", "--export-gcode", str(tmf), "-o", str(OUT / "tmp.gcode")], capture_output=True, text=True)
    if (OUT / "tmp.gcode").exists():
        g = (OUT / "tmp.gcode").read_text()
        print("sliced (2 sets):", re.search(r"filament used \[g\] = ([\d.]+)", g).group(1), "g,",
              re.search(r"estimated printing time \(normal mode\) = (.+)", g).group(1))
    else:
        print("slice failed:", r.stdout[-800:], r.stderr[-800:])
    print(tmf)
    if a.open:
        subprocess.Popen([r"C:\Program Files\Prusa3D\PrusaSlicer\prusa-slicer.exe", str(asm)])
