"""Preview assembly (not for printing): 2 arch brackets + 2020 rails + deck on a slatwall section.
One 3MF object with named parts so PrusaSlicer keeps them together."""
import zipfile
import numpy as np, trimesh
from slathook import SLOT_PITCH, SLOT_OPEN, NECK_TOP

W = 400.0                     # shelf width = rail length
br = trimesh.load("out/print/hanging_arch_rest.stl")
# print frame (x = out of wall, y = up, z = thickness) -> mounted (X = along wall, Y = out, Z = up)
br.apply_transform(np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]], float))
t = br.bounds[1, 0] - br.bounds[0, 0]
parts = {
    "bracket_left": br.copy().apply_translation([20 - br.bounds[0, 0], 0, 0]),
    "bracket_right": br.copy().apply_translation([W - 20 - t - br.bounds[0, 0], 0, 0]),
}
def box(name, x0, x1, y0, y1, z0, z1):
    b = trimesh.creation.box(extents=[x1 - x0, y1 - y0, z1 - z0])
    b.apply_translation([(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2])
    parts[name] = b
top = NECK_TOP
box("rail_back_2020", 0, W, 25, 45, top, top + 20)
box("rail_front_2020", 0, W, 175, 195, top, top + 20)
box("deck_6mm", 0, W, 2, 205, top + 20, top + 26)
# slatwall section: slats between the slot openings (wall face at Y = 0), no booleans needed
slats = [(SLOT_OPEN, 30.0), (-SLOT_PITCH + SLOT_OPEN, 0.0), (-2 * SLOT_PITCH + SLOT_OPEN, -SLOT_PITCH), (-260.0, -2 * SLOT_PITCH)]
for k, (z0, z1) in enumerate(slats):
    box(f"slat_{k + 1}", -50, W + 50, -16, 0, z0, z1)
# one object, one volume per part
verts, faces, vols, off = [], [], [], 0
for name, m in parts.items():
    f0 = len(np.concatenate(faces)) if faces else 0
    verts.append(m.vertices); faces.append(m.faces + off); off += len(m.vertices)
    vols.append((name, f0, f0 + len(m.faces) - 1))
V, F = np.concatenate(verts), np.concatenate(faces)
V = V - [V[:, 0].min() - 10, V[:, 1].min() - 10, V[:, 2].min()]
v = "".join(f'<vertex x="{a:.4f}" y="{b:.4f}" z="{c:.4f}"/>' for a, b, c in V)
tr = "".join(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in F)
model = ('<?xml version="1.0" encoding="UTF-8"?>\n<model unit="millimeter" xml:lang="en-US" '
         'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" xmlns:slic3rpe="http://schemas.slic3r.org/3mf/2017/06">'
         '<metadata name="slic3rpe:Version3mf">1</metadata><resources><object id="1" name="shelf_preview" type="model">'
         f'<mesh><vertices>{v}</vertices><triangles>{tr}</triangles></mesh></object></resources>'
         '<build><item objectid="1" printable="0"/></build></model>')
cfg = ['<?xml version="1.0" encoding="UTF-8"?>\n<config><object id="1" instances_count="1">'
       '<metadata type="object" key="name" value="shelf_preview (not for printing)"/>']
for name, a, b in vols:
    cfg.append(f'<volume firstid="{a}" lastid="{b}"><metadata type="volume" key="name" value="{name}"/></volume>')
cfg.append('</object></config>')
with zipfile.ZipFile("out/print/shelf_preview.3mf", "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8"?>\n<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>')
    z.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Target="/3D/3dmodel.model" Id="rel-1" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')
    z.writestr("3D/3dmodel.model", model)
    z.writestr("Metadata/Slic3r_PE_model.config", "".join(cfg))
print("wrote out/print/shelf_preview.3mf", {k: [round(x) for x in m.extents] for k, m in parts.items()})
