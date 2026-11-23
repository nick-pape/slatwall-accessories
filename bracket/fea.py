"""2D plane-stress FEA on a regular grid of square Q4 elements, with unilateral wall contact.

Coordinates (as mounted, same as slathook): x = out of the wall (wall face at x=0), z = up.
The bracket prints on its side, so every in-plane stress runs along the layers: plane stress
with the bracket's width along the wall as the thickness `t`.

Units: mm, N, MPa.
"""
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

GP = np.array([-1, 1]) / np.sqrt(3)


def _dN(xi, eta, h):
    """Shape-function derivatives d/dx, d/dz for nodes (0,0),(1,0),(1,1),(0,1) of an h-square."""
    dxi = np.array([-(1 - eta), (1 - eta), (1 + eta), -(1 + eta)]) / 4
    deta = np.array([-(1 - xi), -(1 + xi), (1 + xi), (1 - xi)]) / 4
    return dxi * 2 / h, deta * 2 / h


def dmat(E, nu):
    return E / (1 - nu ** 2) * np.array([[1, nu, 0], [nu, 1, 0], [0, 0, (1 - nu) / 2]])


def bmat(xi, eta, h):
    dx, dz = _dN(xi, eta, h)
    B = np.zeros((3, 8))
    B[0, 0::2] = dx
    B[1, 1::2] = dz
    B[2, 0::2] = dz
    B[2, 1::2] = dx
    return B


def ke_q4(E, nu, h, t):
    D = dmat(E, nu)
    K = np.zeros((8, 8))
    for xi in GP:
        for eta in GP:
            B = bmat(xi, eta, h)
            K += B.T @ D @ B * (h * h / 4) * t
    return K


def kg_q4(h, t):
    """Geometric stiffness pieces: Kg_e = sx*Gx + sz*Gz + txz*Gxz (stress taken constant)."""
    Gx, Gz, Gxz = np.zeros((8, 8)), np.zeros((8, 8)), np.zeros((8, 8))
    for xi in GP:
        for eta in GP:
            dx, dz = _dN(xi, eta, h)
            w = (h * h / 4) * t
            for comp in (0, 1):                     # u and w displacement fields
                idx = np.arange(4) * 2 + comp
                Gx[np.ix_(idx, idx)] += np.outer(dx, dx) * w
                Gz[np.ix_(idx, idx)] += np.outer(dz, dz) * w
                Gxz[np.ix_(idx, idx)] += (np.outer(dx, dz) + np.outer(dz, dx)) * w
    return Gx, Gz, Gxz


class Grid:
    """nx x nz elements of size h; lower-left corner at (x0, z0)."""

    def __init__(self, x0, z0, nx, nz, h):
        self.x0, self.z0, self.nx, self.nz, self.h = x0, z0, nx, nz, h
        self.nel = nx * nz
        self.nnode = (nx + 1) * (nz + 1)
        i, j = np.meshgrid(np.arange(nx), np.arange(nz))      # element (row j, col i)
        i, j = i.ravel(), j.ravel()
        n1 = j * (nx + 1) + i
        nodes = np.stack([n1, n1 + 1, n1 + nx + 2, n1 + nx + 1], 1)
        self.edof = np.repeat(nodes * 2, 2, axis=1) + np.tile([0, 1], 4)
        self.xc = x0 + (i + 0.5) * h                          # element centres
        self.zc = z0 + (j + 0.5) * h
        ni, nj = np.meshgrid(np.arange(nx + 1), np.arange(nz + 1))
        self.xn = x0 + ni.ravel() * h                         # node coordinates
        self.zn = z0 + nj.ravel() * h
        self.iK = np.kron(self.edof, np.ones((8, 1), int)).ravel()
        self.jK = np.kron(self.edof, np.ones((1, 8), int)).ravel()

    def field(self, v):
        """Element vector -> 2D image, row 0 at the TOP (for plotting)."""
        return v.reshape(self.nz, self.nx)[::-1]


class Contact:
    """Unilateral supports: list of (dofs, sign). sign=+1: the support stops the DOF going
    negative (pushes +); sign=-1: stops it going positive. Active-set with penalty springs."""

    def __init__(self, groups, kpen):
        self.dofs = np.concatenate([g[0] for g in groups])
        self.sign = np.concatenate([np.full(len(g[0]), g[1]) for g in groups])
        self.active = np.ones(len(self.dofs), bool)
        self.kpen = kpen

    def matrix(self, ndof):
        d = self.dofs[self.active]
        return sp.csc_matrix((np.full(len(d), self.kpen), (d, d)), shape=(ndof, ndof))

    def update(self, u):
        """Return True if the active set changed. Active spring force = -k*u (must push the
        allowed way); inactive DOFs must not penetrate."""
        s = self.sign * u[self.dofs]               # <0 means penetration direction
        new = s < 0
        changed = np.any(new != self.active)
        self.active = new
        return changed


def assemble(grid, Ee, KE):
    vals = (KE.ravel()[None, :] * Ee[:, None]).ravel()
    return sp.csc_matrix((vals, (grid.iK, grid.jK)), shape=(2 * grid.nnode,) * 2)


def solve(grid, Ee, KE, F, contact, max_iter=30):
    """Linear solve with contact active-set iterations. F: (ndof, nload) array.
    Contact state is decided by the first load column (the governing case) per iteration
    when several loads are given; each column gets its own active set."""
    ndof = 2 * grid.nnode
    K0 = assemble(grid, Ee, KE)
    U = np.zeros_like(F)
    actives = []
    for c in range(F.shape[1]):
        for _ in range(max_iter):
            lu = spla.splu((K0 + contact.matrix(ndof)).tocsc())
            u = lu.solve(F[:, c])
            if not contact.update(u):
                break
        U[:, c] = u
        actives.append(contact.active.copy())
    return U, actives


def element_stress(grid, U, E, nu):
    """Centre stresses (sx, sz, txz) per element for displacement vector U (unit density)."""
    B = bmat(0.0, 0.0, grid.h)
    D = dmat(E, nu)
    return (U[grid.edof] @ B.T) @ D.T


def von_mises(s):
    sx, sz, t = s[:, 0], s[:, 1], s[:, 2]
    return np.sqrt(sx ** 2 - sx * sz + sz ** 2 + 3 * t ** 2)
