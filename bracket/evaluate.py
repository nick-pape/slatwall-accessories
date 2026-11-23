"""Evaluate a crisp bracket design in real units: mass, stiffness, stress, hook pull-out force,
linear buckling, and the allowable shelf load per bracket.

Only solid elements are meshed (no void "ghost" material), so buckling modes are physical.
"""
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla
import pypardiso

from fea import Grid, ke_q4, kg_q4, element_stress, von_mises
from model import Bracket, E_PETG, NU

RHO = 1.27e-3          # g/mm^3, PETG
SIGMA_SUSTAINED = 10.0 # MPa: long-term (creep) allowable for PETG along the layers (~20% of UTS)
SIGMA_SHORT = 25.0     # MPa: short-term allowable (UTS ~50 MPa, safety factor 2)
BUCKLE_SF = 3.0        # knock-down for imperfect printed struts


def evaluate(m: Bracket, mask, P=100.0, buckling=True, tf=None):
    """tf: optional per-element thickness factor (element thickness = tf * m.t)."""
    tf = np.ones(m.grid.nel) if tf is None else tf
    """mask: boolean per element (True = material). Returns a dict of results for one bracket
    carrying P newtons of shelf load (load cases: uniform deck, front edge)."""
    g = m.grid
    mask = mask | m.solid
    # keep only material that connects to the hook (drop floating islands)
    from scipy.ndimage import label
    lab, _ = label(mask.reshape(g.nz, g.nx))
    keep = np.unique(lab.ravel()[m.solid & (g.xc < 0)])
    mask = np.isin(lab.ravel(), keep[keep > 0])
    KE = ke_q4(E_PETG, NU, g.h, m.t)
    els = np.where(mask)[0]
    used = np.unique(g.edof[els])
    remap = -np.ones(2 * g.nnode, int); remap[used] = np.arange(len(used))
    edof = remap[g.edof[els]]
    n = len(used)
    iK = np.kron(edof, np.ones((8, 1), int)).ravel(); jK = np.kron(edof, np.ones((1, 8), int)).ravel()
    K0 = sp.csr_matrix(((tf[els][:, None] * KE.ravel()[None, :]).ravel(), (iK, jK)), shape=(n, n))
    contact = m.contact(kpen=E_PETG * m.t * 50)
    ok = np.isin(contact.dofs, used)
    contact.dofs, contact.sign, contact.active = remap[contact.dofs[ok]], contact.sign[ok], contact.active[ok]
    Ffull = m.loads(P)
    res = dict(area=mask[g.xc > 0].sum() * g.h ** 2, mass=tf[mask].sum() * g.h ** 2 * m.t * RHO)
    cases = {}
    for lc, name in enumerate(("uniform", "front")):
        F = Ffull[used, lc]
        for _ in range(40):
            Kc = sp.csr_matrix((np.full(contact.active.sum(), contact.kpen),
                                (contact.dofs[contact.active], contact.dofs[contact.active])), shape=(n, n))
            u = pypardiso.spsolve((K0 + Kc).tocsr(), F)
            if not contact.update(u):
                break
        U = np.zeros(2 * g.nnode); U[used] = u
        s = element_stress(g, U, E_PETG, NU)[els]
        vm = von_mises(s)
        # reactions per contact group
        reac = {}
        off = 0
        for (dofs, sign), key in zip(m.groups, ("floor", "rest", "riser", "wall")):
            d = dofs[np.isin(dofs, used)]
            r = -contact.kpen * U[d] * (sign * U[d] < 0)
            reac[key] = r.sum()
        top = (g.zn == m.top) & (g.xn >= m.depth - 1)
        tip = U[2 * np.where(top)[0] + 1].mean()
        # ignore the single worst elements at re-entrant corners (stress singularities)
        cases[name] = dict(tip_mm=-tip, vm_max=vm.max(), vm_995=np.percentile(vm, 99.5),
                           hook_pull_N=-reac["riser"], wall_push_N=reac["wall"], floor_N=reac["floor"],
                           stress=s, els=els, u=U, active=contact.active.copy())
    res["cases"] = cases
    res["mask"] = mask
    if buckling:
        for name in ("uniform", "front"):
            c = cases[name]
            Gx, Gz, Gxz = kg_q4(g.h, m.t)
            s = c["stress"]
            s = s * tf[els][:, None]
            vals = (np.outer(s[:, 0], Gx.ravel()) + np.outer(s[:, 1], Gz.ravel())
                    + np.outer(s[:, 2], Gxz.ravel())).ravel()
            Kg = sp.csr_matrix((vals, (iK, jK)), shape=(n, n))
            contact.active = c["active"]
            Kc = sp.csr_matrix((np.full(contact.active.sum(), contact.kpen),
                                (contact.dofs[contact.active], contact.dofs[contact.active])), shape=(n, n))
            K = (K0 + Kc).tocsc()
            lu = spla.splu(K, permc_spec="MMD_AT_PLUS_A")
            Minv = spla.LinearOperator(K.shape, matvec=lu.solve)
            # K phi = lam * (-Kg) phi  <=>  (-Kg) phi = (1/lam) K phi ; largest 1/lam
            try:
                th, vec = spla.eigsh(-Kg, k=4, M=K, Minv=Minv, which="LA", tol=1e-6)
                lam = 1.0 / th.max() if th.max() > 0 else np.inf
                mode = np.zeros(2 * g.nnode); mode[used] = vec[:, np.argmax(th)]
                c["mode"] = mode
            except Exception as e:
                lam = np.nan
            c["buckle_factor"] = lam          # critical load = lam * P
    # allowable shelf load per bracket (N): creep on the uniform case, strength on the front case
    u, f = cases["uniform"], cases["front"]
    lim = dict(creep=P * SIGMA_SUSTAINED / u["vm_995"], strength=P * SIGMA_SHORT / f["vm_995"])
    if buckling:
        lim["buckling"] = min(u["buckle_factor"], f["buckle_factor"]) * P / BUCKLE_SF
    res["limits_N"] = lim
    res["allow_N"] = min(lim.values())
    res["allow_kg_per_g"] = res["allow_N"] / 9.81 / res["mass"]
    return res


def summary(name, r):
    u, f = r["cases"]["uniform"], r["cases"]["front"]
    lim = ", ".join(f"{k} {v / 9.81:.1f}" for k, v in r["limits_N"].items())
    return (f"{name:28s} mass {r['mass']:5.1f} g | per 100 N uniform: tip {u['tip_mm']:.2f} mm, "
            f"vm {u['vm_995']:.1f} MPa, hook pull {u['hook_pull_N']:.0f} N | front: vm {f['vm_995']:.1f} | "
            f"buckle x{min(u.get('buckle_factor', np.inf), f.get('buckle_factor', np.inf)):.1f} | "
            f"allow kg: {lim} -> {r['allow_N'] / 9.81:.1f} kg ({r['allow_kg_per_g']:.2f} kg/g)")


if __name__ == "__main__":
    import sys
    from pathlib import Path
    for f in sys.argv[1:]:
        d = np.load(f)
        m = Bracket(depth=float(d["depth"]), z_bottom=float(d["z_bottom"]), h=float(d["h"]), t=float(d["t"]))
        r = evaluate(m, d["xp"] > 0.5)
        print(summary(Path(f).stem, r), flush=True)


def diagnostics_png(m, r, path, case="uniform"):
    """Left: von Mises (per 100 N); right: first buckling mode (displacement magnitude)."""
    from PIL import Image
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    g = m.grid
    c = r["cases"][case]
    vm = np.full(g.nel, np.nan); vm[c["els"]] = von_mises(c["stress"])
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.2))
    ext = [g.x0, g.x0 + g.nx * g.h, g.z0, g.z0 + g.nz * g.h]
    im = ax[0].imshow(g.field(vm), extent=ext, cmap="viridis", vmin=0, vmax=SIGMA_SUSTAINED)
    fig.colorbar(im, ax=ax[0], label="von Mises, MPa per 100 N"); ax[0].set_title(f"stress ({case})")
    if "mode" in c:
        md = c["mode"]; mag = np.hypot(md[0::2], md[1::2])
        el = np.full(g.nel, np.nan); el[c["els"]] = mag[g.edof[c["els"]][:, ::2] // 2].mean(1)
        ax[1].imshow(g.field(el), extent=ext, cmap="magma")
        ax[1].set_title(f"buckling mode (factor {c['buckle_factor']:.2f})")
    for a in ax: a.set_aspect("equal")
    fig.tight_layout()
    save_fig(fig, path, dpi=90)


def save_fig(fig, path, **kw):
    """savefig with retries -- an open Explorer window generating thumbnails can briefly lock
    files on Windows (OSError 22)."""
    import io, time
    import matplotlib.pyplot as plt
    buf = io.BytesIO(); fig.savefig(buf, format="png", **kw); plt.close(fig)
    for i in range(20):
        try:
            open(path, "wb").write(buf.getvalue()); return
        except OSError:
            time.sleep(0.3)
    raise
