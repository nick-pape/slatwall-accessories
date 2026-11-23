"""SIMP topology optimisation of the slatwall bracket (min weighted compliance, volume budget).

Density filter + Heaviside projection (crisp members, minimum member width = filter radius),
OC update, two load cases, contact active set re-evaluated every iteration.

    uv run python bracket/topopt.py --volfrac 0.10 --depth 200
"""
import argparse, json, time
from pathlib import Path
import numpy as np
from scipy.ndimage import convolve
import pypardiso

from fea import ke_q4, assemble
from model import Bracket, E_PETG, NU

OUT = Path(__file__).resolve().parent / "out"


def cone(rmin):
    r = int(np.ceil(rmin))
    dz, dx = np.mgrid[-r:r + 1, -r:r + 1]
    return np.maximum(0.0, rmin - np.hypot(dx, dz))


def project(xt, beta, eta=0.5):
    d = np.tanh(beta * eta) + np.tanh(beta * (1 - eta))
    xp = (np.tanh(beta * eta) + np.tanh(beta * (xt - eta))) / d
    dxp = beta * (1 - np.tanh(beta * (xt - eta)) ** 2) / d
    return xp, dxp


def optimise(depth=200.0, volfrac=0.10, h=1.0, rmin_mm=2.5, t=12.0, weights=(1.0, 1.0),
             iters=220, z_bottom=-130.0, tag=None, log=print, rest=False):
    m = Bracket(depth=depth, z_bottom=z_bottom, h=h, t=t, rest=rest)
    g = m.grid
    KE = ke_q4(1.0, NU, h, t)
    Emin, p = 1e-6, 3.0
    F = m.loads(100.0)
    w = np.asarray(weights, float)
    contacts = [m.contact(kpen=E_PETG * t * 50) for _ in range(F.shape[1])]
    W = cone(rmin_mm / h)
    shape = (g.nz, g.nx)
    Hs = convolve(np.ones(shape), W, mode="constant")
    x = np.where(m.solid, 1.0, np.where(m.design, volfrac, 0.0))
    beta, hist = 1.0, []
    nd = m.design.sum()
    t0 = time.time()
    for it in range(iters):
        if it > 0 and it % 30 == 0 and beta < 32:
            beta *= 2
        xt = convolve(x.reshape(shape), W, mode="constant").ravel() / Hs.ravel()
        xp, dxp = project(xt, beta)
        xp[m.solid], xp[m.void] = 1.0, 0.0
        Ee = E_PETG * (Emin + xp ** p * (1 - Emin))
        K0 = assemble(g, Ee, KE)
        c, dc = 0.0, np.zeros(g.nel)
        for lc in range(F.shape[1]):
            # one solve per load case; the contact active set is updated once per iteration
            # (warm start -- it settles within a few iterations and tracks the design after)
            cs = contacts[lc]
            u = pypardiso.spsolve((K0 + cs.matrix(K0.shape[0])).tocsr(), F[:, lc])
            cs.update(u)
            ue = u[g.edof]
            ce = np.einsum("ij,jk,ik->i", ue, KE, ue)
            c += w[lc] * (Ee * ce).sum()
            dc += w[lc] * (-p * xp ** (p - 1) * (1 - Emin) * E_PETG * ce)
        # chain rule through projection and filter
        dc = dc * dxp
        dc[~m.design] = 0.0
        dc = convolve((dc / Hs.ravel()).reshape(shape), W, mode="constant").ravel()
        dv = np.where(m.design, dxp, 0.0)
        dv = convolve((dv / Hs.ravel()).reshape(shape), W, mode="constant").ravel()
        # OC with bisection on the projected volume
        l1, l2, move = 1e-9, 1e9, 0.1
        xd = x[m.design]
        dcd, dvd = np.minimum(dc[m.design], -1e-30), np.maximum(dv[m.design], 1e-30)
        while (l2 - l1) / (l1 + l2) > 1e-4:
            lm = 0.5 * (l1 + l2)
            xn = np.clip(xd * np.sqrt(-dcd / dvd / lm), np.maximum(0, xd - move), np.minimum(1, xd + move))
            xx = x.copy(); xx[m.design] = xn
            xtt = convolve(xx.reshape(shape), W, mode="constant").ravel() / Hs.ravel()
            vol = project(xtt, beta)[0][m.design].sum() / nd
            l1, l2 = (lm, l2) if vol > volfrac else (l1, lm)
        change = np.abs(xn - xd).max()
        x[m.design] = xn
        hist.append(c)
        if it % 10 == 0 or it == iters - 1:
            log(f"it {it:3d} beta {beta:4.0f} c {c:10.4f} vol {xp[m.design].mean():.3f} "
                f"change {change:.3f} grey {np.mean((xp[m.design] > 0.1) & (xp[m.design] < 0.9)):.3f} "
                f"[{time.time() - t0:.0f}s]")
    res = dict(model=m, xp=xp, compliance=c, hist=hist)
    if tag:
        OUT.mkdir(exist_ok=True)
        np.savez_compressed(OUT / f"{tag}.npz", xp=xp, rest=rest, depth=depth, volfrac=volfrac, h=h, t=t,
                            z_bottom=z_bottom, rmin=rmin_mm, weights=w)
        save_png(m, xp, OUT / f"{tag}.png")
    return res


def save_png(m, xp, path):
    from PIL import Image
    g = m.grid
    img = np.full((g.nz, g.nx, 3), 255, np.uint8)
    f = g.field(xp)
    wall = g.field(((g.xc < 0) & ~m.solid).astype(float))
    img[wall > 0.5] = (215, 218, 224)
    shade = (255 - f[..., None] * np.array([15, 115, 205])).astype(np.uint8)
    body = f > 0.02
    img[body] = shade[body]
    scale = max(1, int(round(3 / m.h)))
    Image.fromarray(img).resize((g.nx * scale, g.nz * scale), Image.NEAREST).save(path)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--depth", type=float, default=200)
    ap.add_argument("--volfrac", type=float, default=0.10)
    ap.add_argument("--h", type=float, default=1.0)
    ap.add_argument("--rmin", type=float, default=2.5)
    ap.add_argument("--iters", type=int, default=220)
    ap.add_argument("--zb", type=float, default=-130)
    ap.add_argument("--w", type=float, nargs=2, default=(1.0, 1.0))
    ap.add_argument("--tag")
    ap.add_argument("--rest", action="store_true")
    a = ap.parse_args()
    tag = a.tag or f"d{a.depth:.0f}_v{a.volfrac:.2f}_zb{-a.zb:.0f}"
    optimise(a.depth, a.volfrac, a.h, a.rmin, iters=a.iters, z_bottom=a.zb, weights=a.w, tag=tag, rest=a.rest)
