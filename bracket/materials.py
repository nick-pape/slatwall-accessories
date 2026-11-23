"""Re-score catalog designs for other filaments (stress pattern is material-independent):
buckling ~ E, creep ~ sustained allowable, strength ~ UTS/2, mass ~ density.
Base run: E 1600 MPa, sustained 10 MPa, short-term 25 MPa, density 1.27."""
import json
M = {  # printed-flat (XY) representative datasheet values; creep allowables are estimates
    "PETG":        dict(E=1600, uts=50, sus=10, rho=1.27),
    "PETG-CF":     dict(E=3500, uts=45, sus=11, rho=1.30),
    "PC Blend":    dict(E=1900, uts=60, sus=15, rho=1.22),
    "PC-CF":       dict(E=2800, uts=55, sus=15, rho=1.22),
    "PET-CF (annealed)": dict(E=5500, uts=70, sus=20, rho=1.32),
}
cat = json.load(open("out/catalog.json"))
rows = {}
for r in sorted(cat, key=lambda r: -r["kg"] / r["mass"]):
    lim, vals = r["limits"], []
    for m in M.values():
        kg = min(lim["creep"] * m["sus"] / 10, lim["strength"] * (m["uts"] / 2) / 25, lim["buckling"] * m["E"] / 1600)
        g = r["mass"] * m["rho"] / 1.27
        vals.append((kg, kg / g))
    rows[r["name"]] = vals
json.dump(dict(materials=M, rows=rows), open("out/materials.json", "w"), indent=1)
for k, v in rows.items(): print(f"{k:18s}", "  ".join(f"{a:5.1f}/{b:.2f}" for a, b in v))
