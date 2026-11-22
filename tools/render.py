"""Render STL previews for the README (OpenGL via trimesh/pyglet; opens a window briefly).

    render.py OUT_DIR part.stl[@mounted] ...

`@mounted` turns a hooked part from its print orientation (on its side) back to how it hangs.
"""
import sys
from pathlib import Path
import numpy as np, trimesh

out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
for arg in sys.argv[2:]:
    f, _, how = arg.partition("@")
    f = Path(f)
    m = trimesh.load(f)
    if how == "mounted":                     # undo slathook.on_side (rotate +90 about Y)
        m.apply_transform(trimesh.transformations.rotation_matrix(np.radians(-90), [0, 1, 0]))
        m.apply_transform(trimesh.transformations.rotation_matrix(np.radians(180), [0, 0, 1]))
    m.apply_translation(-m.bounds.mean(axis=0))
    m.visual.face_colors = [240, 140, 50, 255]
    s = m.scene()
    s.set_camera(angles=(np.radians(55), 0, np.radians(35)), distance=m.scale * 1.25)
    (out / f"{f.stem}.png").write_bytes(s.save_image(resolution=(360, 360), visible=True))
    print("rendered", f.stem)
