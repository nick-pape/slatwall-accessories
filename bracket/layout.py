"""Truss layout optimisation (ground structure + LP) with Euler buckling and print-aware sections.

Every pair of grid nodes is a candidate member. Linear programme per iteration:

    min  sum L_i A_i
    s.t. for each load case k:  B q_k + R_k = -f_k      (node equilibrium, reactions R_k)
                                q_ik <=  sig_t_k * A_i   (tension)
                               -q_ik <=  sig_c_ik * A_i  (compression)

Buckling makes the compressive allowable depend on the section: a printed compression member is
a square w x w (best for Euler with free choice of both dimensions, since the bracket prints flat
and each member can have its own height on the bed). Euler: P_cr = pi^2 E A^2 / (12 L^2).
Requiring P_cr >= SF * |q| gives sig_c = |q|/A <= pi^2 E A / (12 SF L^2), updated from the
previous iterate (sequential LP). Long thin compression members become expensive, so the
optimiser shortens them by bracing.

Supports (unilateral, as on the real wall):
  * hook bar root, nodes (0, NECK_TOP) and (0, 0): pull toward the wall (Rx <= 0), carry load up (Rz >= 0)
  * wall face, nodes (0, z<0) outside slot openings: push only (Rx >= 0), frictionless
"""
import math, sys, time
from pathlib import Path
import numpy as np
import scipy.sparse as sp
from scipy.optimize import linprog

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from slathook import NECK_TOP, SLOT_PITCH, SLOT_OPEN

E = 2000.0
SIG_T = {"uniform": 10.0, "front": 20.0}     # MPa: sustained (creep) / short-term
BUCKLE_SF = 3.0
# Compression section options:
#   "square": solid w x w.             P_cr = pi^2 E A^2 / (12 L^2)       (needs SLP)
#   "twin":   two perimeter walls S apart, laced by cross-ribs (a ladder / crane-boom section).
#             I = A S^2 / 4  ->  P_cr = pi^2 E A S^2 / (4 L^2)  -> allowable stress independent of A.
TWIN_S = 16.0   # mm between the two walls (centre to centre)


def ground_structure(depth=200.0, z_bottom=-120.0, sx=10.0, sz=10.0, max_len=1e9):
    xs = np.arange(0.0, depth + 1e-6, sx)
    zs = [NECK_TOP, 0.0] + list(np.arange(-sz, z_bottom - 1e-6, -sz))
    zs = np.array(zs)
    X, Z = np.meshgrid(xs, zs)
    nodes = np.stack([X.ravel(), Z.ravel()], 1)
    ix = np.round(nodes[:, 0] / sx).astype(int)
    iz = np.array([list(zs).index(z) for z in nodes[:, 1]])
    mem = []
    n = len(nodes)
    for a in range(n):
        for b in range(a + 1, n):
            dx, dz = ix[b] - ix[a], iz[b] - iz[a]
            if math.gcd(abs(dx), abs(dz)) != 1:        # would pass through another node
                continue
            L = np.hypot(*(nodes[b] - nodes[a]))
            if L <= max_len:
                mem.append((a, b, L))
    mem = np.array(mem)
    return nodes, mem[:, :2].astype(int), mem[:, 2]


def effective_lengths(nodes, M, L, A, supports, rel=1e-2):
    """Buckling length per member: a compression member whose end node is braced by nothing
    except collinear members buckles together with them, so walk along collinear active
    members through such 'unbraced' nodes and sum the lengths."""
    act = A > rel * A.max()
    d = (nodes[M[:, 1]] - nodes[M[:, 0]]) / L[:, None]
    by_node = [[] for _ in range(len(nodes))]
    for i in np.where(act)[0]:
        by_node[M[i, 0]].append(i); by_node[M[i, 1]].append(i)
    def unbraced(k):
        if k in supports or len(by_node[k]) < 2:
            return False
        u = d[by_node[k][0]]
        return all(abs(u[0] * d[j][1] - u[1] * d[j][0]) < 1e-6 for j in by_node[k])
    Le = L.copy()
    for i in np.where(act)[0]:
        tot = L[i]
        for end in (0, 1):
            k, prev = M[i, end], i
            seen = {i}
            while unbraced(k):
                nxt = [j for j in by_node[k] if j not in seen]
                if not nxt:
                    break
                j = nxt[0]; seen.add(j); tot += L[j]
                k = M[j, 1] if M[j, 0] == k else M[j, 0]
        Le[i] = tot
    return Le


def solve(depth=200.0, z_bottom=-120.0, P=100.0, sx=10.0, sz=10.0, iters=40, joint=0.0, section="twin", load_dx=40.0, log=print):
    """joint: extra volume (mm^3) charged per member used -- reweighted-L1 sparsity, so the
    optimiser trades a little volume for far fewer members (joints, print overhead)."""
    nodes, M, L = ground_structure(depth, z_bottom, sx, sz)
    n, m = len(nodes), len(M)
    d = (nodes[M[:, 1]] - nodes[M[:, 0]]) / L[:, None]
    # equilibrium matrix B (2n x m): member force q (tension +) acts on node a along +d, b along -d
    rows = np.concatenate([2 * M[:, 0], 2 * M[:, 0] + 1, 2 * M[:, 1], 2 * M[:, 1] + 1])
    cols = np.tile(np.arange(m), 4)
    vals = np.concatenate([d[:, 0], d[:, 1], -d[:, 0], -d[:, 1]])
    B = sp.csr_matrix((vals, (rows, cols)), shape=(2 * n, m))
    # reactions
    on_wall = np.isclose(nodes[:, 0], 0)
    hook = np.where(on_wall & (nodes[:, 1] >= -1e-6))[0]
    slots = [(-k * SLOT_PITCH - 0.5, -k * SLOT_PITCH + SLOT_OPEN + 0.5) for k in range(1, 3)]
    wall = np.where(on_wall & (nodes[:, 1] < -1e-6)
                    & ~np.array([any(a <= z <= b for a, b in slots) for z in nodes[:, 1]]))[0]
    rdofs, rlo, rhi = [], [], []
    for k in hook:
        rdofs += [2 * k, 2 * k + 1]; rlo += [-np.inf, 0.0]; rhi += [0.0, np.inf]
    for k in wall:
        rdofs += [2 * k]; rlo += [0.0]; rhi += [np.inf]
    nr = len(rdofs)
    supports = set(hook) | set(wall)
    R = sp.csr_matrix((np.ones(nr), (rdofs, np.arange(nr))), shape=(2 * n, nr))
    # loads
    top = np.where(np.isclose(nodes[:, 1], NECK_TOP) & (nodes[:, 0] > 0)
                   & np.isclose(np.mod(nodes[:, 0] + 1e-6, load_dx), 0, atol=1e-3))[0]
    f_uni = np.zeros(2 * n); f_uni[2 * top + 1] = -P / len(top)
    f_tip = np.zeros(2 * n); f_tip[2 * top[np.argmax(nodes[top, 0])] + 1] = -P
    cases = {"uniform": f_uni, "front": f_tip}
    nc = len(cases)
    # variables: [A (m), q_k (m each), r_k (nr each)]
    nv = m + nc * (m + nr)
    c = np.concatenate([L, np.zeros(nc * (m + nr))])
    blocks = []
    for k in range(nc):
        row = [sp.csr_matrix((2 * n, m))]
        for j in range(nc):
            row += [B if j == k else sp.csr_matrix((2 * n, m)), R if j == k else sp.csr_matrix((2 * n, nr))]
        blocks.append(sp.hstack(row))
    Aeq = sp.vstack(blocks).tocsr()
    beq = np.concatenate([-f for f in cases.values()])
    bounds = [(0, None)] * m
    for k in range(nc):
        bounds += [(None, None)] * m + list(zip(rlo, rhi))
    I = sp.identity(m, format="csr")
    sig_c = np.full((nc, m), 1e-3)                 # start: compression very expensive...
    A_prev = None
    names = list(cases)
    t0 = time.time()
    for it in range(iters):
        if A_prev is not None:
            # Euler allowable from the previous section (square), capped by material strength;
            # damped so the SLP doesn't oscillate
            Le = effective_lengths(nodes, M, L, A_prev, supports)
            if section == "twin":
                sig_e = math.pi ** 2 * E * TWIN_S ** 2 / (4 * BUCKLE_SF * Le ** 2)
            else:
                sig_e = math.pi ** 2 * E * np.maximum(A_prev, 1e-3) / (12 * BUCKLE_SF * Le ** 2)
            for k, nm in enumerate(names):
                sig_c[k] = 0.5 * sig_c[k] + 0.5 * np.minimum(SIG_T[nm], sig_e)
        else:
            for k, nm in enumerate(names):
                sig_c[k] = np.minimum(SIG_T[nm], math.pi ** 2 * E * (TWIN_S ** 2 / 4 if section == "twin" else 10.0 / 12)
                                      / (BUCKLE_SF * L ** 2))
        if A_prev is not None and joint > 0:
            c[:m] = L + joint / (A_prev + 0.5)            # cost ~ L*A + joint*[A > 0]
        ub_rows = []
        for k, nm in enumerate(names):
            # q - sig_t A <= 0 ;  -q - sig_c A <= 0
            for sgn, sig in ((+1, np.full(m, SIG_T[nm])), (-1, sig_c[k])):
                row = [-sp.diags(sig)]
                for j in range(nc):
                    row += [sgn * I if j == k else sp.csr_matrix((m, m)), sp.csr_matrix((m, nr))]
                ub_rows.append(sp.hstack(row))
        Aub = sp.vstack(ub_rows).tocsr()
        res = linprog(c, A_ub=Aub, b_ub=np.zeros(Aub.shape[0]), A_eq=Aeq, b_eq=beq,
                      bounds=bounds, method="highs")
        if res.status != 0:
            raise RuntimeError(res.message)
        A = res.x[:m]
        Q = np.stack([res.x[m + k * (m + nr): m + k * (m + nr) + m] for k in range(nc)])
        vol = (A * L).sum()
        log(f"it {it:2d} volume {vol:8.0f} mm^3 (+{joint * (A > 1e-2 * A.max()).sum():.0f} joints) members {(A > 1e-3 * A.max()).sum():4d} [{time.time() - t0:.0f}s]")
        if it > 8 and A_prev is not None and np.abs(A - A_prev).max() < 1e-3 * A.max():
            break
        A_prev = A
    keep = A > 1e-2 * A.max()
    return dict(nodes=nodes, M=M[keep], L=L[keep], A=A[keep], Q=Q[:, keep], names=names,
                volume=vol, wall=wall, hook=hook)


if __name__ == "__main__":
    import argparse, pickle
    ap = argparse.ArgumentParser()
    ap.add_argument("--depth", type=float, default=200)
    ap.add_argument("--zb", type=float, default=-120)
    ap.add_argument("--P", type=float, default=100)
    ap.add_argument("--s", type=float, default=10)
    ap.add_argument("--joint", type=float, default=0)
    ap.add_argument("--section", default="twin")
    a = ap.parse_args()
    r = solve(a.depth, a.zb, a.P, a.s, a.s, joint=a.joint, section=a.section)
    out = Path(__file__).resolve().parent / "out"
    out.mkdir(exist_ok=True)
    tag = f"truss_{a.section}_d{a.depth:.0f}_zb{-a.zb:.0f}_j{a.joint:.0f}"
    pickle.dump(r, open(out / f"{tag}.pkl", "wb"))
    print(f"{tag}: volume {r['volume']:.0f} mm^3 = {r['volume'] * 1.27e-3:.1f} g, {len(r['A'])} members")
