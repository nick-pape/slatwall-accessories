"""Infill-defined shelf: model three SOLID BARS (deck, wall spine, diagonal), let the slicer's infill
pattern be the lacing inside them. The middle of the triangle is empty.

The body is a solid triangle (deck / wall / diagonal faces) + hook + rest tab, printed with
0 perimeters and no top skin, so the infill pattern IS the truss and shows on the end face.
Modifier meshes add structure back where it matters:
  * solid zones (100%): hook, top joint, nose, foot
  * skins (100%, ~2 lines): deck top, wall face, diagonal outer face

    uv run python infill_shelf.py WIDTH DEPTH --pattern honeycomb --density 20
Writes out/print/infill_<pattern>_<W>x<D>.3mf (object + modifiers, settings embedded).
"""
import argparse, math, zipfile
from pathlib import Path
import numpy as np
from shapely.geometry import Polygon, box, LineString
from shapely.ops import unary_union

from catalog import RF, TOP, HOOKP
from model import REST_TAB

HERE = Path(__file__).parent
SKIN = 1.3          # ~2 lines of 0.68 mm


def bars(depth, Hb=10.0, joint_r=2.0):
    """Three solid bars (deck, wall spine, diagonal) + rounded joints + hook + rest tab. Empty middle.
    Returns body, solid zone (hook/joints/tab), outer skins, inner skins."""
    from shapely.geometry import Point
    half = Hb / 2
    A = np.array([half, TOP - half]); B = np.array([depth - half, TOP - half]); C = np.array([half, RF + half])
    segs = {"deck": (A, B), "spine": (C, A), "diag": (C, B)}
    bar = {k: LineString([p, q]).buffer(half, cap_style=2) for k, (p, q) in segs.items()}
    allb = unary_union(list(bar.values()))
    R = Hb + 4
    joints = [allb.intersection(Point(V).buffer(R)).convex_hull.buffer(-joint_r, join_style=1).buffer(joint_r, join_style=1)
              for V in (A, B, C)]
    tab = box(-REST_TAB[0], RF, 0.01, RF + REST_TAB[1])
    foot = box(0, RF, Hb, RF + Hb + 2).buffer(-1.5, join_style=1).buffer(1.5, join_style=1).union(box(0, RF, 2, RF + Hb + 2))
    joints.append(foot)                                             # tab fully backed by the foot joint
    body = unary_union([allb] + joints).intersection(box(0, -1e3, depth, TOP))
    body = unary_union([body, HOOKP, tab])
    centroid = (A + B + C) / 3
    outer, inner = [], []
    for k, (p, q) in segs.items():
        u = (q - p) / np.linalg.norm(q - p); n = np.array([-u[1], u[0]])
        for sgn in (1, -1):
            off = n * sgn * (half - SKIN / 2)
            face = LineString([p + off, q + off]).buffer(SKIN / 2, cap_style=2)
            mid = (p + q) / 2 + off
            (inner if np.dot(centroid - (p + q) / 2, n * sgn) > 0 else outer).append(face)
    solid = unary_union(joints + [HOOKP, tab, box(0, 0, Hb, TOP)])
    return body, solid, unary_union(outer).intersection(body), unary_union(inner).intersection(body)


def extrude_mesh(poly, h):
    """Watertight prism mesh (trimesh) of a shapely polygon, extruded 0..h in Z (print frame)."""
    import trimesh
    meshes = [trimesh.creation.extrude_polygon(p, h) for p in getattr(poly, "geoms", [poly]) if p.area > 0.01]
    return trimesh.util.concatenate(meshes)


def write_3mf(path, parts, obj_cfg, name):
    """parts: [(name, mesh, volume_type, {key: value})]; one object, per-volume settings."""
    verts, faces, vols, off, f0 = [], [], [], 0, 0
    for nm, m, vt, cfg in parts:
        verts.append(m.vertices); faces.append(m.faces + off); off += len(m.vertices)
        vols.append((nm, vt, cfg, f0, f0 + len(m.faces) - 1)); f0 += len(m.faces)
    V, F = np.concatenate(verts), np.concatenate(faces)
    V = V - [V[:, 0].min() - 20, V[:, 1].min() - 20, 0]
    v = "".join(f'<vertex x="{a:.4f}" y="{b:.4f}" z="{c:.4f}"/>' for a, b, c in V)
    t = "".join(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in F)
    model = ('<?xml version="1.0" encoding="UTF-8"?>\n<model unit="millimeter" xml:lang="en-US" '
             'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" xmlns:slic3rpe="http://schemas.slic3r.org/3mf/2017/06">'
             '<metadata name="slic3rpe:Version3mf">1</metadata><resources>'
             f'<object id="1" name="{name}" type="model"><mesh><vertices>{v}</vertices><triangles>{t}</triangles></mesh></object>'
             '</resources><build><item objectid="1" transform="1 0 0 0 1 0 0 0 1 0 0 0" printable="1"/></build></model>')
    cfg = ['<?xml version="1.0" encoding="UTF-8"?>\n<config><object id="1" instances_count="1">',
           f'<metadata type="object" key="name" value="{name}"/>']
    cfg += [f'<metadata type="object" key="{k}" value="{v}"/>' for k, v in obj_cfg.items()]
    for nm, vt, vc, a, b in vols:
        cfg.append(f'<volume firstid="{a}" lastid="{b}"><metadata type="volume" key="name" value="{nm}"/>'
                   f'<metadata type="volume" key="volume_type" value="{vt}"/>'
                   + ('<metadata type="volume" key="modifier" value="1"/>' if vt == "ParameterModifier" else "")
                   + "".join(f'<metadata type="volume" key="{k}" value="{v}"/>' for k, v in vc.items())
                   + "</volume>")
    cfg.append("</object></config>")
    base = [l for l in (HERE.parent / "tools/prusa/cfg_extruded.ini").read_text().splitlines() if l and not l.startswith("#")]
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8"?>\n<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>')
        z.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Target="/3D/3dmodel.model" Id="rel-1" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')
        z.writestr("3D/3dmodel.model", model)
        z.writestr("Metadata/Slic3r_PE.config", "; generated\n" + "".join(f"; {l}\n" for l in base))
        z.writestr("Metadata/Slic3r_PE_model.config", "".join(cfg))


def build(width, depth, pattern, density, Hb=10.0):
    body, solid, outer, inner = bars(depth, Hb)
    solid_cfg = {"fill_density": "100%", "fill_pattern": "rectilinear", "perimeters": "2"}
    skin_cfg = {"fill_density": "100%", "fill_pattern": "rectilinear"}
    parts = [("body (3 bars)", extrude_mesh(body, width), "ModelPart", {}),
             ("solid: hook, joints, rest tab", extrude_mesh(solid.buffer(0.3), width + 1), "ParameterModifier", solid_cfg),
             ("skins: outer faces", extrude_mesh(outer, width + 1), "ParameterModifier", skin_cfg),
             ("skins: inner faces", extrude_mesh(inner, width + 1), "ParameterModifier", skin_cfg)]
    obj = {"perimeters": "0", "top_solid_layers": "0", "bottom_solid_layers": "2",
           "fill_pattern": pattern, "fill_density": f"{density}%", "infill_every_layers": "1"}
    out = HERE / "out" / "print" / f"infill_{pattern}_{width:.0f}x{depth:.0f}.3mf"
    write_3mf(out, parts, obj, f"infill shelf {pattern} {density}%")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("width", type=float); ap.add_argument("depth", type=float)
    ap.add_argument("--pattern", default="honeycomb")
    ap.add_argument("--density", type=float, default=20)
    ap.add_argument("--bar", type=float, default=10.0, help="bar depth (mm)")
    a = ap.parse_args()
    print("wrote", build(a.width, a.depth, a.pattern, a.density, a.bar))
