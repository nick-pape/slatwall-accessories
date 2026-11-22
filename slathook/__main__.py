"""uv run python -m slathook  ->  hook/ : profile (DXF, SVG), STEP bodies, fit-test STL."""
from pathlib import Path
from build123d import *
from .hook import HOOK, hook_profile_pts, hook_part, fit_test

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "hook"


def dims_svg(pts, path, k=14.0):
    """Side view of the hook with the key dimensions, for the README (works in light/dark)."""
    h = HOOK
    X = lambda y: 60 + (y + 16) * k            # mm -> px; wall face at y=0
    Y = lambda z: 40 + (21 - z) * k
    poly = " ".join(f"{X(y):.1f},{Y(z):.1f}" for y, z in pts)
    g = "#8a8f98"
    def dim(x1, y1, x2, y2, label, dx=0, dy=0, anchor="middle"):
        return (f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{g}" '
                f'stroke-width="1.2" marker-start="url(#a)" marker-end="url(#a)"/>'
                f'<text x="{(x1 + x2) / 2 + dx:.1f}" y="{(y1 + y2) / 2 + dy:.1f}" fill="{g}" '
                f'font-size="15" text-anchor="{anchor}" font-family="sans-serif">{label}</text>')
    wall = (f'<rect x="{X(-16):.1f}" y="{Y(0):.1f}" width="{16 * k}" height="{6 * k}" fill="{g}" opacity="0.25"/>'
            f'<rect x="{X(-4.3):.1f}" y="{Y(30):.1f}" width="{4.3 * k:.1f}" '
            f'height="{(30 - 10) * k:.1f}" fill="{g}" opacity="0.25"/>')
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{X(6) + 90:.0f}" height="{Y(-6) + 10:.0f}" '
        f'viewBox="0 0 {X(6) + 90:.0f} {Y(-6) + 10:.0f}">',
        f'<defs><marker id="a" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" '
        f'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{g}"/></marker></defs>',
        wall,
        f'<polygon points="{poly}" fill="#f08c32" stroke="#b35f12" stroke-width="1.5"/>',
        f'<line x1="{X(0):.1f}" y1="{Y(-6):.1f}" x2="{X(0):.1f}" y2="{Y(24):.1f}" stroke="{g}" stroke-dasharray="5 4"/>',
        f'<text x="{X(0) + 6:.1f}" y="{Y(23):.1f}" fill="{g}" font-size="13" font-family="sans-serif">wall face</text>',
        dim(X(4.5), Y(0), X(4.5), Y(10), "slot 10", 8, 5, "start"),
        dim(X(h["yb"]), Y(-1.5), X(0), Y(-1.5), f'{-h["yb"]:g}', 0, 20),
        dim(X(1.2), Y(0), X(1.2), Y(h["hb"]), f'{h["hb"]:g}', 6, 5, "start"),
        dim(X(h["yb"]) - 25, Y(0), X(h["yb"]) - 25, Y(h["ztop"]), f'{h["ztop"]:g}', -8, 5, "end"),
        f'<text x="{X(-9.2):.1f}" y="{Y(20.3):.1f}" fill="{g}" font-size="15" text-anchor="middle" '
        f'font-family="sans-serif">riser {h["w"]:g}, lean {h["lean"]:.2f}</text>',
        f'<text x="{X(h["yb"] + 3.2):.1f}" y="{Y(3):.1f}" fill="#5a3200" font-size="14" font-family="sans-serif">R{h["roll"]:g}</text>',
        '</svg>']
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(parts))


def main():
    OUT.mkdir(exist_ok=True)
    # 2D profile (Y-Z plane drawn as X-Y: X = out of wall, Y = up), no overlap tab
    pts = hook_profile_pts(0.0, 0.0, HOOK["hs"], HOOK)
    flat = Face(Wire.make_polygon([Vector(y, z, 0) for y, z in pts], close=True))
    for exp, ext in ((ExportDXF(unit=Unit.MM), "dxf"), (ExportSVG(unit=Unit.MM), "svg")):
        exp.add_layer("hook") if ext == "dxf" else None
        exp.add_shape(flat, layer="hook" if ext == "dxf" else "")
        exp.write(str(OUT / f"hook_profile.{ext}"))
    dims_svg(pts, ROOT / "docs" / "img" / "hook_profile.svg")
    for w in (10, 20):
        export_step(hook_part(w), str(OUT / f"hook_{w}mm.step"))
    export_stl(fit_test(), str(OUT / "fit_test.stl"))
    print("wrote", ", ".join(sorted(p.name for p in OUT.iterdir())))


if __name__ == "__main__":
    main()
