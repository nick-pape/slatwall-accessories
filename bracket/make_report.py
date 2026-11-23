"""Build the bracket study report (single self-contained HTML page with embedded images)."""
import base64, io, json
from pathlib import Path
from PIL import Image

HERE = Path(__file__).parent
OUT = HERE / "out"
REPORT = HERE / "report" / "bracket_study.html"

STYLE = {"beautiful": "Beautiful", "optimized": "Optimized", "minimalist": "Minimalist", "organic": "Organic"}
TITLES = {"minimal_two_bars": "Two bars", "salginatobel": "Salginatobel arch", "victorian": "Victorian cast iron",
          "forth_bridge": "Forth Bridge", "hanging_arch": "Hanging arch", "hanging_arch_rest": "Hanging arch + rest",
          "twin_triangle": "Twin-wall triangle", "gaudi_tree": "Gaudí tree", "bone": "Bone"}
BLURB = {
    "salginatobel": "Robert Maillart's 1930 Swiss deck-arch bridge, turned into a cantilever: a slim rib that thickens toward the wall, with evenly spaced columns up to a thin deck. Beautiful, but a solid curved rib is an expensive way to carry compression.",
    "victorian": "The cast-iron bracket under an old railway-station canopy: a wall post, a concave sweep and rings in the corner. The sweep carries load in bending rather than straight compression, so it needs a lot of plastic.",
    "forth_bridge": "The 1890 Forth Bridge cantilever: a deep curved bottom chord, a straight top chord and X-braced panels. The most efficient of the beautiful designs; its slender X-bracing is what eventually buckles.",
    "hanging_arch": "What the truss optimizer kept pointing at: a twin-wall ladder arch carries the compression, a fan of thin ties hangs everything from the hook, and short posts hold the deck. Every thin member is an exact number of perimeters.",
    "hanging_arch_rest": "Your two suggestions applied to the hanging arch: the arch foot now sits in the next slot down, and a spine along the wall was offered to the search. The rest tab helps (about 7% better). The search dropped the spine because it adds weight without raising the buckling limit, but a thin 2-perimeter spine (about 3 g) is still worth adding for real use: it keeps the tab seated if the shelf is knocked upward.",
    "twin_triangle": "The textbook triangle with a twin-wall ladder strut running straight into the lower-slot rest. Sound, but the long straight strut needs a wide, heavy ladder to stop it buckling.",
    "minimal_two_bars": "A deck and one strut into the lower slot. Nothing else. The rest tab does so much work that this lands mid-pack, and it is the easiest to print and the stiffest of the lot.",
    "gaudi_tree": "Gaudí's branching columns from the Sagrada Família: a trunk rising from the lower slot that splits twice into curved branches holding the deck at evenly spaced points.",
    "bone": "Pure topology optimization with the lower-slot rest, smoothed into an organic form. It rediscovers the triangle, adds a tension tie from the hook, and leaves a few tiny holes where material wasn't needed.",
}


def data_uri(path, max_w=900, crop_left_half=False, fmt="PNG"):
    im = Image.open(path)
    if crop_left_half:
        im = im.crop((0, 0, im.width // 2, im.height))
    if im.width > max_w:
        im = im.resize((max_w, int(im.height * max_w / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    if fmt == "JPEG":
        im.convert("RGB").save(buf, "JPEG", quality=84)
        mime = "jpeg"
    else:
        im.save(buf, "PNG", optimize=True)
        mime = "png"
    return f"data:image/{mime};base64," + base64.b64encode(buf.getvalue()).decode()


def bar_chart(rows):
    """Horizontal bars of kg-per-gram (one series, one hue), values labelled at the bar end."""
    rows = sorted(rows, key=lambda r: -r["kg"] / r["mass"])
    W, row_h, left, right = 640, 30, 170, 70
    H = row_h * len(rows) + 34
    vmax = 0.35
    x = lambda v: left + (W - left - right) * v / vmax
    parts = [f'<svg viewBox="0 0 {W} {H}" class="chart" role="img" aria-label="Safe load per gram of PETG for each design">']
    for v in (0, 0.1, 0.2, 0.3):
        parts.append(f'<line x1="{x(v):.1f}" y1="6" x2="{x(v):.1f}" y2="{H - 24}" class="grid"/>'
                     f'<text x="{x(v):.1f}" y="{H - 8}" class="tick" text-anchor="middle">{v:.1f}</text>')
    for i, r in enumerate(rows):
        y = 8 + i * row_h
        val = r["kg"] / r["mass"]
        w = x(val) - x(0)
        top = i == 0
        parts.append(
            f'<g class="bar{" lead" if top else ""}"><title>{TITLES[r["name"]]}: {r["kg"]:.1f} kg safe on {r["mass"]:.0f} g = {val:.2f} kg/g</title>'
            f'<rect x="{left - 160}" y="{y - 3}" width="{W - 20}" height="{row_h}" class="hit"/>'
            f'<text x="{left - 10}" y="{y + 15}" class="lbl" text-anchor="end">{TITLES[r["name"]]}</text>'
            f'<path d="M{x(0):.1f},{y + 4} h{w - 4:.1f} a4,4 0 0 1 4,4 v10 a4,4 0 0 1 -4,4 h{-(w - 4):.1f} z" class="mark"/>'
            f'<text x="{x(val) + 8:.1f}" y="{y + 15}" class="val">{val:.2f}</text></g>')
    parts.append('</svg>')
    return "".join(parts)


def card(r, imgs):
    lim = r["limits"]
    gov = r["governs"]
    bars = "".join(
        f'<div class="lim{" gov" if k == gov else ""}"><span>{k}</span><b>{v:.1f} kg</b></div>' for k, v in lim.items())
    return f'''
<article class="design" id="{r["name"]}">
  <header>
    <span class="chip {r["style"]}">{STYLE[r["style"]]}</span>
    <h3>{TITLES[r["name"]]}</h3>
  </header>
  <figure class="sil"><img src="{imgs["sil"]}" alt="{TITLES[r["name"]]} side profile"></figure>
  <div class="nums">
    <div><b>{r["mass"]:.0f} g</b><span>PETG</span></div>
    <div><b>{r["kg"]:.1f} kg</b><span>safe per bracket</span></div>
    <div><b>{r["kg"] / r["mass"]:.2f}</b><span>kg per g</span></div>
  </div>
  <p>{BLURB[r["name"]]}</p>
  <div class="lims">{bars}</div>
  <p class="meta">{r["t"]:.0f} mm wide, hook {r["t_hook"]:.0f} mm · deck sags {r["tip_mm_10kg"]:.1f} mm at the tip under 10 kg{" · rests in the next slot down" if r["rest"] else ""}</p>
  <details>
    <summary>Stress map and 3D view</summary>
    <div class="pair">
      <figure class="plate"><img src="{imgs["diag"]}" alt="stress map"><figcaption>Stress under an even 10 kg shelf load. Yellow is the creep limit (10 MPa).</figcaption></figure>
      <figure><img src="{imgs["r3d"]}" alt="3D render"><figcaption>As printed: lying flat, profile on the bed.</figcaption></figure>
    </div>
  </details>
</article>'''


def main():
    cat = json.load(open(OUT / "catalog.json"))
    by = {r["name"]: r for r in cat}
    imgs = {}
    for r in cat:
        n = r["name"]
        imgs[n] = dict(sil=data_uri(OUT / f"sil_{n}.png", 620),
                       diag=data_uri(OUT / f"cat_{n}_diag.png", 700, crop_left_half=True),
                       r3d=data_uri(OUT / "r3d" / f"bracket_{n}.png", 360))
    proc = dict(simp=data_uri(OUT / "d200_v0.10_zb130.png", 640),
                truss1=data_uri(OUT / "truss_d200_zb120_P100.png", 640, fmt="JPEG"),
                truss2=data_uri(OUT / "truss_twin_d200_zb120_j400.png", 640, fmt="JPEG"),
                arch=data_uri(OUT / "arch_b_diag.png", 900, fmt="JPEG"))
    best = max(cat, key=lambda r: r["kg"] / r["mass"])
    mats = json.load(open(OUT / "materials.json"))
    mat_names = list(mats["materials"])
    mat_rows = "".join(
        f'<tr><th scope="row">{TITLES[d]}</th>' + "".join(
            f'<td><b>{v[0]:.1f}</b> kg <span class="muted">{v[1]:.2f}</span></td>' for v in vals) + "</tr>"
        for d, vals in mats["rows"].items())
    mat_head = "".join(f"<th scope='col'>{m}</th>" for m in mat_names)
    mat_props = "".join(f"<td>{p['E'] / 1000:.1f} GPa · {p['sus']:.0f} MPa · {p['rho']:.2f}</td>" for p in mats["materials"].values())
    table_rows = "".join(
        f'<tr><th scope="row"><a href="#{r["name"]}">{TITLES[r["name"]]}</a></th><td>{STYLE[r["style"]]}</td>'
        f'<td>{r["mass"]:.0f} g</td><td>{r["kg"]:.1f} kg</td><td>{r["kg"] / r["mass"]:.2f}</td><td>{r["governs"]}</td></tr>'
        for r in sorted(cat, key=lambda r: -r["kg"] / r["mass"]))
    order = [n for n in ["hanging_arch", "hanging_arch_rest", "bone", "gaudi_tree", "minimal_two_bars", "forth_bridge",
                         "twin_triangle", "victorian", "salginatobel"] if n in by]
    cards = "".join(card(by[n], imgs[n]) for n in order)
    html = TEMPLATE
    for k, v in dict(CHART=bar_chart(cat), CARDS=cards, TABLE=table_rows, MATHEAD=mat_head, MATPROPS=mat_props,
                     MATROWS=mat_rows, SIMP=proc["simp"], TRUSS1=proc["truss1"], TRUSS2=proc["truss2"],
                     ARCH=proc["arch"], BEST=TITLES[best["name"]], BESTG=f'{best["mass"]:.0f}',
                     BESTKG=f'{best["kg"]:.1f}', BESTR=f'{best["kg"] / best["mass"]:.2f}',
                     HEROIMG=imgs[best["name"]]["sil"]).items():
        html = html.replace("{{" + k + "}}", v)
    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text(html, encoding="utf-8")
    print("wrote", REPORT, f"{len(html) / 1e6:.1f} MB")


TEMPLATE = r'''<title>Slatwall Bracket Study</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;700;800&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
/* Layout: a single engineering-notebook column; designs as a two-up card grid. */
:root {
  --bg: #f6f7f9; --panel: #ffffff; --fg: #1b2230; --muted: #5b6577; --line: #dde1e8;
  --accent: #1d4ed8; --accent-soft: #e3eafc; --mark: #1d4ed8;
  --beautiful: #c2410c; --optimized: #1d4ed8; --minimalist: #374151; --organic: #15803d;
  --chip-fg: #ffffff; --plate: #ffffff;
  --display: "Archivo", "Helvetica Neue", Arial, sans-serif;
  --body: "IBM Plex Sans", "Segoe UI", system-ui, sans-serif;
  --mono: "IBM Plex Mono", ui-monospace, "Cascadia Mono", Consolas, monospace;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg: #11151c; --panel: #181e27; --fg: #e6e9ef; --muted: #9aa4b5; --line: #2a3240;
  --accent: #7aa2ff; --accent-soft: #1d2840; --mark: #7aa2ff;
  --beautiful: #f08a4b; --optimized: #7aa2ff; --minimalist: #b6bfcc; --organic: #4cc27a;
  --chip-fg: #11151c; --plate: #f3f4f6; color-scheme: dark } }
:root[data-theme="dark"] {
  --bg: #11151c; --panel: #181e27; --fg: #e6e9ef; --muted: #9aa4b5; --line: #2a3240;
  --accent: #7aa2ff; --accent-soft: #1d2840; --mark: #7aa2ff;
  --beautiful: #f08a4b; --optimized: #7aa2ff; --minimalist: #b6bfcc; --organic: #4cc27a;
  --chip-fg: #11151c; --plate: #f3f4f6; color-scheme: dark }
body { background: var(--bg); color: var(--fg); font: 16px/1.6 var(--body);
  padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px)); }
main { max-width: 1040px; margin: 0 auto; padding-block: 40px 80px; display: grid; gap: 56px; }
h1, h2, h3 { font-family: var(--display); text-wrap: balance; line-height: 1.15; margin: 0; }
h1 { font-size: clamp(2rem, 5vw, 3.1rem); font-weight: 800; letter-spacing: -0.01em; }
h2 { font-size: 1.6rem; font-weight: 700; }
h3 { font-size: 1.2rem; font-weight: 700; }
p { margin: 0; max-width: 68ch; }
a { color: var(--accent); }
section { display: grid; gap: 18px; }
.eyebrow { font: 500 0.78rem/1 var(--mono); letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); }
.hero { display: grid; grid-template-columns: 1.1fr 1fr; gap: 32px; align-items: center; }
.hero .lede { font-size: 1.12rem; color: var(--muted); }
.hero figure { margin: 0; }
.kpis { display: flex; flex-wrap: wrap; gap: 28px; margin-top: 8px; }
.kpis div { display: grid; }
.kpis b { font: 700 1.9rem/1.1 var(--display); font-variant-numeric: tabular-nums; }
.kpis span { color: var(--muted); font-size: 0.85rem; }
.panel { background: var(--panel); border: 1px solid var(--line); border-radius: 10px; padding: 20px; }
.chart { width: 100%; height: auto; display: block; }
.chart .grid { stroke: var(--line); stroke-width: 1; }
.chart .tick { fill: var(--muted); font: 12px var(--mono); }
.chart .lbl { fill: var(--fg); font: 14px var(--body); }
.chart .val { fill: var(--fg); font: 500 13px var(--mono); }
.chart .mark { fill: var(--mark); opacity: 0.55; }
.chart .lead .mark { opacity: 1; }
.chart .hit { fill: transparent; }
.chart .bar:hover .mark { opacity: 1; }
.chart .bar:hover .lbl { font-weight: 600; }
.findings { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; }
.findings div { display: grid; gap: 6px; align-content: start; }
.findings h3 { font-size: 1.02rem; }
.findings p { color: var(--muted); font-size: 0.95rem; }
.designs { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 460px), 1fr)); gap: 20px; }
.design { background: var(--panel); border: 1px solid var(--line); border-radius: 10px; padding: 20px; display: grid; gap: 12px; align-content: start; min-width: 0; }
.design header { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.chip { font: 600 0.72rem/1 var(--mono); letter-spacing: 0.06em; text-transform: uppercase; color: var(--chip-fg); padding: 5px 8px; border-radius: 4px; }
.chip.beautiful { background: var(--beautiful); } .chip.optimized { background: var(--optimized); }
.chip.minimalist { background: var(--minimalist); } .chip.organic { background: var(--organic); }
.design figure { margin: 0; }
.sil img { width: 100%; display: block; }
.nums { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; border-block: 1px solid var(--line); padding-block: 10px; }
.nums div { display: grid; }
.nums b { font: 700 1.35rem/1.2 var(--display); font-variant-numeric: tabular-nums; }
.nums span { font-size: 0.78rem; color: var(--muted); }
.design p { font-size: 0.95rem; }
.lims { display: flex; gap: 8px; flex-wrap: wrap; }
.lim { font: 0.8rem var(--mono); border: 1px solid var(--line); border-radius: 4px; padding: 4px 8px; display: flex; gap: 6px; }
.lim span { color: var(--muted); }
.lim.gov { border-color: var(--accent); background: var(--accent-soft); }
.meta { color: var(--muted); font-size: 0.85rem !important; }
details summary { cursor: pointer; color: var(--accent); font-weight: 500; }
details summary:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.pair { display: grid; grid-template-columns: 1.6fr 1fr; gap: 12px; margin-top: 12px; align-items: start; }
.pair img { width: 100%; display: block; border-radius: 6px; }
.plate img { background: var(--plate); }
figcaption { font-size: 0.8rem; color: var(--muted); margin-top: 4px; }
.scroll { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; font-size: 0.92rem; font-variant-numeric: tabular-nums; }
th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--line); white-space: nowrap; }
thead th { font: 500 0.75rem var(--mono); text-transform: uppercase; letter-spacing: 0.06em; color: var(--muted); }
.muted { color: var(--muted); font-family: var(--mono); font-size: 0.8rem; }
.steps { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 300px), 1fr)); gap: 16px; }
.steps figure { margin: 0; display: grid; gap: 6px; }
.steps img { width: 100%; border-radius: 6px; background: var(--plate); display: block; }
.steps figcaption { font-size: 0.88rem; }
ul { margin: 0; padding-left: 1.2em; display: grid; gap: 6px; max-width: 72ch; }
code { font: 0.88em var(--mono); background: var(--accent-soft); padding: 1px 5px; border-radius: 4px; }
@media (max-width: 720px) { .hero, .pair { grid-template-columns: 1fr; } }
@media (prefers-reduced-motion: reduce) { * { transition: none !important; } }
</style>
<main>

<section class="hero">
  <div style="display:grid;gap:14px;min-width:0">
    <span class="eyebrow">Slatwall · Prusa MK4 · PETG</span>
    <h1>Slatwall Bracket Study</h1>
    <p class="lede">How light can a 3D-printed shelf bracket get and still hold a loaded 200&nbsp;mm shelf for years? Nine designs, from Maillart and Gaudí to pure optimization, all sized for the same job and checked with the same physics.</p>
    <div class="kpis">
      <div><b>{{BESTG}} g</b><span>best bracket ({{BEST}})</span></div>
      <div><b>{{BESTKG}} kg</b><span>safe load, per bracket</span></div>
      <div><b>{{BESTR}}</b><span>kg held per gram</span></div>
    </div>
  </div>
  <figure><img src="{{HEROIMG}}" alt="Best bracket profile against the wall"></figure>
</section>

<section>
  <span class="eyebrow">The job</span>
  <h2>One bracket, one shelf, one printer</h2>
  <ul>
    <li><b>Shelf:</b> 200&nbsp;mm deep, load spread along the top or all on the front edge. Two brackets per shelf; numbers below are per bracket.</li>
    <li><b>Wall:</b> slatwall verified to fit ProSlat carbon fiber panels, slots 10&nbsp;mm open at a measured 4&nbsp;3/4" (120.65&nbsp;mm) pitch. Every bracket uses our fit-tested hook in the upper slot; most also rest a tab in the next slot down.</li>
    <li><b>Printer:</b> MK4 with the 0.6 HF nozzle. The bracket prints flat, so it has to fit the 250&nbsp;×&nbsp;210&nbsp;mm bed: about 215&nbsp;×&nbsp;150&nbsp;mm, two slots tall at most.</li>
    <li><b>"Safe":</b> the smallest of three limits. Creep: stress under 10&nbsp;MPa so it doesn't sag over months. Strength: half of PETG's tensile strength. Buckling: a factor of 3 on the load where a strut bows out.</li>
  </ul>
</section>

<section>
  <span class="eyebrow">Results</span>
  <h2>Load per gram of plastic</h2>
  <div class="panel"><p class="muted" style="margin-bottom:6px">Safe load (kg) per gram of PETG · higher is better · hover a bar for details</p>{{CHART}}</div>
  <div class="scroll"><table>
    <thead><tr><th>Design</th><th>Style</th><th>PETG</th><th>Safe load</th><th>kg / g</th><th>Limited by</th></tr></thead>
    <tbody>{{TABLE}}</tbody>
  </table></div>
</section>

<section>
  <span class="eyebrow">What the physics says</span>
  <h2>Findings</h2>
  <div class="findings">
    <div><h3>Height beats everything</h3><p>The hook gets pulled out with roughly load × depth ÷ bracket height. A bracket one slot tall pulls the hook 2.5× harder than one reaching toward the next slot, so every good design uses the full two-slot height.</p></div>
    <div><h3>Buckling, not breaking</h3><p>PETG is soft (about 1.6 GPa). Long thin struts bow sideways long before the plastic tears. Most designs end up limited by buckling or by creep, almost never by strength.</p></div>
    <div><h3>The wall only pushes</h3><p>A frictionless wall can't hold anything up, which forced the optimizer into hanging ties. Resting a tab in the next slot down gives a second support that carries weight, and makes even two bars competitive.</p></div>
    <div><h3>Build members from perimeters</h3><p>Thin members are sized to an exact number of perimeters (1.17, 1.74 or 2.30&nbsp;mm), so they print as continuous loops with no infill: the strongest thing a printer makes.</p></div>
    <div><h3>Twin walls for compression</h3><p>Two perimeter walls held apart by zig-zag lacing, like a crane boom, resist bowing far better per gram than a solid strut. That ladder arch is what puts the hanging arch on top.</p></div>
    <div><h3>Thickness is free</h3><p>The part prints flat, so the hook region can be printed taller than the truss at no cost. The hook is the most stressed spot on every design.</p></div>
  </div>
</section>

<section>
  <span class="eyebrow">Catalog</span>
  <h2>The designs</h2>
  <p>Each design was sized by an automated search: least plastic that still holds about 15&nbsp;kg (some land a bit under after correcting PETG's stiffness). Every candidate was checked with the full simulation.</p>
  <div class="designs">{{CARDS}}</div>
</section>

<section>
  <span class="eyebrow">How we got here</span>
  <h2>From a blob to a truss</h2>
  <div class="steps">
    <figure><img src="{{SIMP}}" alt="topology optimization result"><figcaption><b>1. Topology optimization.</b> Shape-optimizing a block of plastic for stiffness gives a truss, but its thin curved strut buckles at 8 kg.</figcaption></figure>
    <figure><img src="{{TRUSS1}}" alt="first truss layout"><figcaption><b>2. Truss layout with buckling.</b> Thousands of candidate bars, solved for the lightest set. It found a loophole: a chain of short bars with unbraced joints. Fixed, it still came out as a strange hanging shape.</figcaption></figure>
    <figure><img src="{{TRUSS2}}" alt="twin-wall truss layout"><figcaption><b>3. Twin-wall struts.</b> Giving compression members a ladder section reveals the pattern: an arch below, ties fanning from the hook, the deck on top.</figcaption></figure>
    <figure><img src="{{ARCH}}" alt="hanging arch stress and buckling"><figcaption><b>4. Clean parametric design.</b> The pattern drawn cleanly, then tuned by search. Left: stress. Right: where it would buckle first.</figcaption></figure>
  </div>
</section>

<section>
  <span class="eyebrow">Materials</span>
  <h2>Same shapes, other filaments</h2>
  <p>A design's stress pattern doesn't depend on the material, so each design can be re-scored from its PETG simulation: buckling scales with stiffness, creep and strength with each material's allowables, and weight with density. Shapes stay as sized for PETG; a stiffer material would let them get thinner still.</p>
  <div class="scroll"><table>
    <thead><tr><th>Design</th>{{MATHEAD}}</tr></thead>
    <tbody><tr><th scope="row" class="muted">stiffness · creep limit · density</th>{{MATPROPS}}</tr>{{MATROWS}}</tbody>
  </table></div>
  <p class="meta">Each cell: safe load per bracket, then kg per gram. Values are printed-flat datasheet figures; brands vary widely (PETG-CF stiffness is quoted anywhere from 2.5 to 4.9 GPa). PET-CF needs annealing to reach these numbers. Creep limits per material are estimates.</p>
</section>

<section>
  <span class="eyebrow">Fine print</span>
  <h2>Method and limits</h2>
  <ul>
    <li><b>Simulation:</b> 2D plane-stress finite elements on a 0.4&nbsp;mm grid of the printed profile. The bracket prints flat, so every in-plane load runs along the layers. Wall contact is one-sided: the hook bears on the slot floor and lip, the bracket pushes on the wall face, the rest tab sits on the lower slot floor.</li>
    <li><b>Buckling:</b> linear eigenvalue analysis of the actual geometry (solid material only), safety factor 3.</li>
    <li><b>Checked against beam theory</b> (tip deflection within 0.3%). The rest tab and hook were checked for tilt-in insertion with a separate motion simulator.</li>
    <li><b>Not modelled:</b> twisting out of the bracket's plane (the shelf deck tying two brackets together handles that), stress at sharp joints (small fillets are added), print defects, and temperature. Treat absolute numbers as ±20% until a load test; the ranking is the reliable part.</li>
    <li><b>Material:</b> Prusament PETG, 1.6&nbsp;GPa, 0.15&nbsp;mm layers. Sizing searches ran at 2.0&nbsp;GPa and all final numbers were re-checked at 1.6.</li>
  </ul>
</section>

<section>
  <span class="eyebrow">Next</span>
  <h2>What to print</h2>
  <ul>
    <li>Print the leading design and the two-bar minimalist in PETG and load-test both with water jugs on a short shelf: add 2&nbsp;kg at a time, and note the deflection at the tip and anything that creaks.</li>
    <li>If you want more margin without more weight, print the same file in PC-CF or annealed PET-CF.</li>
    <li>Print-ready: <code>bracket/out/print/hanging_arch_rest.3mf</code> (0.40&nbsp;mm STRUCTURAL, PETG, 3 perimeters, 100% infill, about 1&nbsp;h&nbsp;22&nbsp;m, 45&nbsp;g). Re-sized for 0.40&nbsp;mm perimeters and given a thin wall spine: 14.4&nbsp;kg safe per bracket.</li>
    <li>Everything lives in <code>bracket/</code> of the slatwall-accessories repo: the solver, every design, and STLs for all of them.</li>
  </ul>
</section>

</main>
'''

if __name__ == "__main__":
    main()
