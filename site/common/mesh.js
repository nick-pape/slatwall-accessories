// Watertight prism meshes from 2D outlines, plus binary STL and PrusaSlicer 3MF writers.
// Shared by every generator on the site.
import earcut from "https://cdn.jsdelivr.net/npm/earcut@2.2.4/+esm";

const area2 = (r) => { let a = 0; for (let i = 0; i < r.length; i++) { const [x0, y0] = r[i], [x1, y1] = r[(i + 1) % r.length]; a += x0 * y1 - x1 * y0; } return a; };
const ccw = (r, want) => ((area2(r) > 0) === want ? r : r.slice().reverse());
// Drop repeated and collinear vertices: they make zero-area cap triangles and open edges.
function clean(r, eps = 1e-3) {
  let pts = r.slice(), changed = true;
  while (changed && pts.length > 3) {
    changed = false;
    for (let i = 0; i < pts.length && pts.length > 3; i++) {
      const a = pts[(i - 1 + pts.length) % pts.length], b = pts[i], c = pts[(i + 1) % pts.length];
      const cross = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0]);
      if (Math.abs(cross) < eps * Math.max(1, Math.hypot(c[0] - a[0], c[1] - a[1]))) { pts.splice(i, 1); changed = true; i--; }
    }
  }
  return pts;
}

// earcut can run a triangle edge straight through another vertex that sits on the same line (ladder walls
// are long collinear runs), leaving a T-junction = an open edge. Split triangles at any such vertex.
function splitT(tris, pts, eps = 1e-4) {
  const out = [], stack = tris.slice();
  while (stack.length) {
    const t = stack.pop();
    let hit = null;
    for (let e = 0; e < 3 && !hit; e++) {
      const i = t[e], j = t[(e + 1) % 3], k = t[(e + 2) % 3], [ax, ay] = pts[i], [bx, by] = pts[j];
      const dx = bx - ax, dy = by - ay, L2 = dx * dx + dy * dy;
      if (L2 === 0) continue;
      for (let v = 0; v < pts.length; v++) {
        if (v === i || v === j) continue;
        const [px, py] = pts[v], s = ((px - ax) * dx + (py - ay) * dy) / L2;
        if (s <= 1e-9 || s >= 1 - 1e-9) continue;
        const cr = (px - ax) * dy - (py - ay) * dx;
        if (cr * cr <= eps * eps * L2) { hit = [[i, v, k], [v, j, k]]; break; }
      }
    }
    if (hit) stack.push(...hit); else out.push(t);
  }
  return out;
}

// Extrude polygons [{outer:[[u,v]..], holes:[[[u,v]..]..]}] from w0 to w1.
// `map(u, v, w)` places a point in XYZ (must keep handedness: identity or a cyclic axis permutation).
export function extrude(polys, w0, w1, map = (u, v, w) => [u, v, w]) {
  const tris = [];
  const push = (a, b, c) => tris.push(...a, ...b, ...c);
  for (const p of polys) {
    const outer = ccw(clean(p.outer), true), holes = (p.holes || []).map((h) => ccw(clean(h), false)).filter((h) => h.length >= 3);
    const rings = [outer, ...holes];
    const flat = [], holeIdx = [];
    for (const r of rings) { if (r !== outer) holeIdx.push(flat.length / 2); for (const [u, v] of r) flat.push(u, v); }
    const pts = rings.flat();
    const idx = earcut(flat, holeIdx, 2);
    const cap = [];
    for (let i = 0; i < idx.length; i += 3) cap.push([idx[i], idx[i + 1], idx[i + 2]]);
    for (const [ia, ib, ic] of splitT(cap, pts)) {
      let [a, b, c] = [pts[ia], pts[ib], pts[ic]];
      if (Math.abs(area2([a, b, c])) < 1e-9) continue;                 // sliver left over from collinear vertices
      if (area2([a, b, c]) < 0) [b, c] = [c, b];                        // force CCW (seen from +w)
      push(map(...a, w1), map(...b, w1), map(...c, w1));                // top cap, normal +w
      push(map(...a, w0), map(...c, w0), map(...b, w0));                // bottom cap, normal -w
    }
    for (const r of rings) {
      for (let i = 0; i < r.length; i++) {
        const a = r[i], b = r[(i + 1) % r.length];
        const a0 = map(...a, w0), b0 = map(...b, w0), a1 = map(...a, w1), b1 = map(...b, w1);
        push(a0, b0, b1); push(a0, b1, a1);
      }
    }
  }
  return new Float32Array(tris);
}

export const concat = (...arrs) => { const out = new Float32Array(arrs.reduce((n, a) => n + a.length, 0)); let o = 0; for (const a of arrs) { out.set(a, o); o += a.length; } return out; };

export function bounds(tris) {
  const lo = [Infinity, Infinity, Infinity], hi = [-Infinity, -Infinity, -Infinity];
  for (let i = 0; i < tris.length; i += 3) for (let k = 0; k < 3; k++) { lo[k] = Math.min(lo[k], tris[i + k]); hi[k] = Math.max(hi[k], tris[i + k]); }
  return [lo, hi];
}

export const translate = (tris, d) => { const t = tris.slice(); for (let i = 0; i < t.length; i += 3) { t[i] += d[0]; t[i + 1] += d[1]; t[i + 2] += d[2]; } return t; };

export function stl(tris, name = "part") {
  const n = tris.length / 9, buf = new ArrayBuffer(84 + 50 * n), dv = new DataView(buf);
  new TextEncoder().encodeInto(name.slice(0, 79), new Uint8Array(buf, 0, 80));
  dv.setUint32(80, n, true);
  for (let t = 0; t < n; t++) {
    const o = 84 + 50 * t, v = tris.subarray(9 * t, 9 * t + 9);
    const ux = v[3] - v[0], uy = v[4] - v[1], uz = v[5] - v[2], wx = v[6] - v[0], wy = v[7] - v[1], wz = v[8] - v[2];
    let nx = uy * wz - uz * wy, ny = uz * wx - ux * wz, nz = ux * wy - uy * wx; const l = Math.hypot(nx, ny, nz) || 1;
    [nx / l, ny / l, nz / l, ...v].forEach((x, k) => dv.setFloat32(o + 4 * k, x, true));
  }
  return new Blob([buf], { type: "model/stl" });
}

// ---- 3MF (PrusaSlicer project: one object, named volumes, print settings embedded) ----
function indexed(tris) {
  const key = new Map(), verts = [], faces = [];
  for (let i = 0; i < tris.length; i += 9) {
    const f = [];
    for (let k = 0; k < 9; k += 3) {
      const x = tris[i + k], y = tris[i + k + 1], z = tris[i + k + 2], s = `${x.toFixed(4)},${y.toFixed(4)},${z.toFixed(4)}`;
      let id = key.get(s); if (id === undefined) { id = verts.length; key.set(s, id); verts.push([x, y, z]); }
      f.push(id);
    }
    if (f[0] !== f[1] && f[1] !== f[2] && f[0] !== f[2]) faces.push(f);
  }
  return { verts, faces };
}

const CRC = (() => { const t = new Uint32Array(256); for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; } return t; })();
const crc32 = (b) => { let c = 0xffffffff; for (const x of b) c = CRC[(c ^ x) & 255] ^ (c >>> 8); return (c ^ 0xffffffff) >>> 0; };

function zip(files) {                                       // stored (no compression) zip
  const enc = new TextEncoder(), parts = [], central = []; let off = 0;
  for (const [name, text] of files) {
    const n = enc.encode(name), d = typeof text === "string" ? enc.encode(text) : text, c = crc32(d);
    const h = new DataView(new ArrayBuffer(30));
    h.setUint32(0, 0x04034b50, true); h.setUint16(4, 20, true); h.setUint32(14, c, true);
    h.setUint32(18, d.length, true); h.setUint32(22, d.length, true); h.setUint16(26, n.length, true);
    parts.push(h.buffer, n, d);
    const e = new DataView(new ArrayBuffer(46));
    e.setUint32(0, 0x02014b50, true); e.setUint16(4, 20, true); e.setUint16(6, 20, true); e.setUint32(16, c, true);
    e.setUint32(20, d.length, true); e.setUint32(24, d.length, true); e.setUint16(28, n.length, true); e.setUint32(42, off, true);
    central.push(e.buffer, n);
    off += 30 + n.length + d.length;
  }
  const size = central.reduce((s, x) => s + x.byteLength, 0), end = new DataView(new ArrayBuffer(22));
  end.setUint32(0, 0x06054b50, true); end.setUint16(8, files.length, true); end.setUint16(10, files.length, true);
  end.setUint32(12, size, true); end.setUint32(16, off, true);
  return new Blob([...parts, ...central, end.buffer], { type: "model/3mf" });
}

// volumes: [{name, tris}] in print coordinates (Z up, on the bed). ini: PrusaSlicer config text ("key = value" lines).
export function threemf(volumes, ini, name, bed = [250, 210]) {
  const vols = []; let f0 = 0;
  const V = [], F = [];
  for (const v of volumes) {
    const { verts, faces } = indexed(v.tris), base = V.length;
    V.push(...verts); faces.forEach((f) => F.push(f.map((i) => i + base)));
    vols.push([v.name, f0, f0 + faces.length - 1]); f0 += faces.length;
  }
  const lo = [Infinity, Infinity, Infinity], hi = [-Infinity, -Infinity, -Infinity];
  for (const p of V) for (let k = 0; k < 3; k++) { lo[k] = Math.min(lo[k], p[k]); hi[k] = Math.max(hi[k], p[k]); }
  const d = [bed[0] / 2 - (lo[0] + hi[0]) / 2, bed[1] / 2 - (lo[1] + hi[1]) / 2, -lo[2]];
  const esc = (s) => s.replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");
  const vx = V.map(([x, y, z]) => `<vertex x="${(x + d[0]).toFixed(4)}" y="${(y + d[1]).toFixed(4)}" z="${(z + d[2]).toFixed(4)}"/>`).join("");
  const tr = F.map(([a, b, c]) => `<triangle v1="${a}" v2="${b}" v3="${c}"/>`).join("");
  const model = '<?xml version="1.0" encoding="UTF-8"?>\n<model unit="millimeter" xml:lang="en-US" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" xmlns:slic3rpe="http://schemas.slic3r.org/3mf/2017/06">'
    + '<metadata name="slic3rpe:Version3mf">1</metadata><resources>'
    + `<object id="1" name="${esc(name)}" type="model"><mesh><vertices>${vx}</vertices><triangles>${tr}</triangles></mesh></object>`
    + '</resources><build><item objectid="1" transform="1 0 0 0 1 0 0 0 1 0 0 0" printable="1"/></build></model>';
  const cfg = ['<?xml version="1.0" encoding="UTF-8"?>\n<config><object id="1" instances_count="1">', `<metadata type="object" key="name" value="${esc(name)}"/>`];
  for (const [nm, a, b] of vols)
    cfg.push(`<volume firstid="${a}" lastid="${b}"><metadata type="volume" key="name" value="${esc(nm)}"/><metadata type="volume" key="volume_type" value="ModelPart"/></volume>`);
  cfg.push("</object></config>");
  const conf = "; generated by the slatwall accessories web generator\n" + ini.split(/\r?\n/).filter((l) => l && !l.startsWith("#")).map((l) => `; ${l}\n`).join("");
  return zip([
    ["[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8"?>\n<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>'],
    ["_rels/.rels", '<?xml version="1.0" encoding="UTF-8"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Target="/3D/3dmodel.model" Id="rel-1" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>'],
    ["3D/3dmodel.model", model],
    ["Metadata/Slic3r_PE.config", conf],
    ["Metadata/Slic3r_PE_model.config", cfg.join("")],
  ]);
}

export function download(blob, filename) {
  const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = filename;
  document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 5000);
}
