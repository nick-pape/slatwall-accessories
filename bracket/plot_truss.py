"""Draw a layout result: line width ~ section width, red = compression, blue = tension."""
import pickle, sys
from pathlib import Path
import numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

def draw(r, path, title=""):
    nodes, M, A, Q = r["nodes"], r["M"], r["A"], r["Q"]
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.axvspan(-18, 0, color="#d7dae0")
    for (a, b), Ai, q in zip(M, A, Q.T):
        qq = q[np.argmax(np.abs(q))]
        col = "#c0392b" if qq < 0 else "#2471a3"
        w = np.sqrt(Ai)  # mm (square-ish section)
        ax.plot(*nodes[[a, b]].T, color=col, lw=max(0.4, w * 1.2), solid_capstyle="round")
    ax.set_aspect("equal"); ax.set_title(title, fontsize=10)
    ax.set_xlabel("out from wall (mm)"); ax.set_ylabel("height (mm)")
    fig.tight_layout(); fig.savefig(path, dpi=110); plt.close(fig)

if __name__ == "__main__":
    for f in sys.argv[1:]:
        r = pickle.load(open(f, "rb"))
        draw(r, Path(f).with_suffix(".png"), f"{Path(f).stem}: {r['volume'] * 1.27e-3:.1f} g, {len(r['A'])} members")
