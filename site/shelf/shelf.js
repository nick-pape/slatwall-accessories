import { extrude, concat, stl, threemf, download } from "../common/mesh.js";
import { Viewer } from "../common/viewer.js";

const $ = (id) => document.getElementById(id);
const status = (t) => { $("status").textContent = t || ""; $("status").hidden = !t; };
const inch = (mm) => `${(mm / 25.4).toFixed(2)}″`;
const NAMES = {
  L20: "L bracket, 20 mm wall spine", L30: "L bracket, 30 mm wall spine", L45: "L bracket, 45 mm wall spine",
  L60: "L bracket, 60 mm wall spine", T45: "Truss, 45° brace pushing on the wall", T55: "Truss, 55° brace pushing on the wall",
  slot: "Truss, brace foot resting in the next slot down",
};

// table grams are solid-equivalent; PrusaSlicer comes in at 0.67-0.79 of that (2 lines + gyroid inside)
const SLICED = 0.72;
const viewer = new Viewer($("view"));
let py, ini, current = null, mode = "water";

// ---- inputs: each slider mirrors a number box ----
for (const k of ["width", "depth", "water", "kg", "lip"]) {
  $(k + "-r").addEventListener("input", () => { $(k).value = $(k + "-r").value; schedule(); });
  $(k).addEventListener("input", () => { $(k + "-r").value = $(k).value; schedule(); });
}
const setMode = (m) => {
  mode = m; $("m-water").classList.toggle("on", m === "water"); $("m-kg").classList.toggle("on", m === "kg");
  $("f-water").hidden = m !== "water"; $("f-kg").hidden = m !== "kg"; schedule();
};
$("m-water").onclick = () => setMode("water"); $("m-kg").onclick = () => setMode("kg");
const setView = (m) => { $("v-mount").classList.toggle("on", m === "mounted"); $("v-print").classList.toggle("on", m === "printed"); viewer.setMode(m); };
$("v-mount").onclick = () => setView("mounted"); $("v-print").onclick = () => setView("printed");

const num = (k, lo, hi) => Math.min(hi, Math.max(lo, parseFloat($(k).value) || lo));
function params() {
  const width = num("width", 20, 220), depth = num("depth", +$("depth").min, +$("depth").max);
  const water = num("water", 1, 60), lip = num("lip", 0, 10);
  const load = mode === "water" ? (width / 10) * (depth / 10) * water / 1000 : num("kg", 0.1, 50);
  return { width, depth, lip, load };
}

let timer;
function schedule() {
  const p = params();
  $("width-in").textContent = inch(p.width); $("depth-in").textContent = inch(p.depth);
  $("water-kg").textContent = `= ${p.load.toFixed(2)} kg`;
  clearTimeout(timer); timer = setTimeout(run, 120);
}

function stat(v, label) { return `<div class="stat"><b>${v}</b><span>${label}</span></div>`; }

function run() {
  if (!py) return;
  const p = params();
  const t0 = performance.now();
  const r = JSON.parse(py.globals.get("generate")(p.width, p.depth, p.load, p.lip));
  if (!r.ok) {
    current = null; $("dl-stl").disabled = $("dl-3mf").disabled = true;
    $("stats").innerHTML = `<p class="bad">No design carries ${p.load.toFixed(1)} kg at ${p.depth.toFixed(0)} mm deep and ${p.width.toFixed(0)} mm wide. Try a lower load, a wider shelf or a shallower one.</p>`;
    return;
  }
  // print frame: X = out from the wall, Y = up (as mounted), Z = along the wall (= print height)
  const body = extrude(r.profile, 0, p.width);
  // side lips: quad in (profile z, print Z), run along X; (u, v, w) -> (X = w, Y = u, Z = v) is a cyclic swap
  const lips = r.side_lips.map((l) => extrude([{ outer: l.quad, holes: [] }], l.x0, l.x1, (u, v, w) => [w, u, v]));
  current = { p, r, body, lips };
  viewer.show(concat(body, ...lips), { wall: { pitch: r.slot_pitch, open: r.slot_open, lip: 4.3 }, keepView: !!run.shown });
  run.shown = true;
  status("");
  const d = r.design;
  $("stats").innerHTML = [
    stat(`${d.kg.toFixed(1)} kg`, `safe load (rated ${p.load.toFixed(1)} kg)`),
    stat(`≈ ${Math.round(d.grams)} g`, "PETG (estimate)"),
    stat(`${d.perims} × ${d.S} mm`, "perimeters × ladder gap"),
    stat(NAMES[d.name] || d.name, "shape"),
  ].join("");
  $("dl-stl").disabled = $("dl-3mf").disabled = false;
  console.debug(`generated in ${(performance.now() - t0).toFixed(0)} ms`);
}

const fname = () => { const { p } = current; return `slatwall_shelf_${p.width.toFixed(0)}x${p.depth.toFixed(0)}${p.lip > 0 ? `_lip${p.lip}` : ""}`; };
$("dl-stl").onclick = () => current && download(stl(concat(current.body, ...current.lips), fname()), fname() + ".stl");
$("dl-3mf").onclick = () => current && download(threemf(
  [{ name: "shelf", tris: current.body }, ...current.lips.map((t, i) => ({ name: `lip ${i + 1}`, tris: t }))],
  ini, fname()), fname() + ".3mf");

async function boot() {
  schedule();
  try {
    py = await loadPyodide({ indexURL: "https://cdn.jsdelivr.net/pyodide/v0.29.5/full/" });
    status("Loading geometry libraries…");
    await py.loadPackage(["numpy", "shapely"]);
    const files = { "slathook/__init__.py": "../py/slathook/__init__.py", "slathook/profile.py": "../py/slathook/profile.py",
                    "shelf_geom.py": "../py/shelf_geom.py", "shelf_web.py": "shelf_web.py" };
    py.FS.mkdirTree("/app/slathook");
    const [table, cfg] = await Promise.all([fetch("table.json").then((r) => r.text()), fetch("../common/printer.ini").then((r) => r.text()),
      ...Object.entries(files).map(async ([dst, src]) => py.FS.writeFile("/app/" + dst, await (await fetch(src)).text()))]);
    ini = cfg;
    py.runPython("import sys; sys.path.insert(0, '/app')\nfrom shelf_web import load_table, generate");
    const lim = py.globals.get("load_table")(table).toJs({ dict_converter: Object.fromEntries });
    for (const k of ["depth", "depth-r"]) { $(k).min = lim.min_depth; $(k).max = lim.max_depth; }
    status("Generating…");
    run();
  } catch (e) {
    console.error(e); status("Couldn't start the generator: " + e.message);
  }
}
boot();
