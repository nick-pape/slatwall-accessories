"""Offline capacity table for the browser shelf generator.

The FEA is a 2D profile x width (plane stress, thickness = width), so every limit (creep, strength,
buckling, sag) and the mass scale exactly with width: one solve per (depth, candidate, size) gives
kg per mm of width for any shelf width. The browser then only looks designs up (shelf_geom.pick).

    uv run python shelf_table.py [--workers 6]      # resumable; writes ../site/shelf/table.json
"""
import argparse, json, os, time, warnings
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE.parent / "site" / "shelf" / "table.json"
DEPTHS = list(range(30, 151, 5)) + list(range(160, 231, 10))
REF_W = 100.0


def solve(job):
    warnings.filterwarnings("ignore")
    from shelf_gen import evaluate_geom
    from shelf_geom import design
    d, name, perims, S = job
    geom, bottom = design(name, d, S, perims)
    kg, mass, lim = evaluate_geom(geom, d, REF_W, bottom, name == "slot")
    return job, dict(name=name, perims=perims, S=S, kg_per_mm=round(kg / REF_W, 6),
                     g_per_mm=round(mass / REF_W, 5), limit=min(lim, key=lim.get))


def main():
    from shelf_geom import candidates, SIZES
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    table = json.loads(OUT.read_text()) if OUT.exists() else {}
    rows = table.get("rows", {})
    done = {(int(d), r["name"], r["perims"], r["S"]) for d, rs in rows.items() for r in rs}
    jobs = [(d, n, p, S) for d in DEPTHS for n, _ in candidates(d) for p, S in SIZES if (d, n, p, S) not in done]
    print(f"{len(jobs)} solves to run ({len(done)} cached)", flush=True)
    os.environ.setdefault("MKL_NUM_THREADS", "2"); os.environ.setdefault("OMP_NUM_THREADS", "2")
    t0 = time.time()

    def save():
        OUT.parent.mkdir(parents=True, exist_ok=True)
        key = lambda r: (r["name"], r["perims"], r["S"])
        OUT.write_text(json.dumps({
            "about": "Safe load (kg) and solid-equivalent mass (g) per mm of shelf width, from shelf_table.py "
                     "(2D FEA: creep 10 MPa, strength/2, buckling/3, tip sag <= depth/300).",
            "depths": sorted(int(d) for d in rows), "sizes": [list(s) for s in SIZES],
            "rows": {str(d): sorted(rows[str(d)], key=key) for d in sorted(int(d) for d in rows)}}, indent=0))

    with ProcessPoolExecutor(a.workers) as ex:
        futs = [ex.submit(solve, j) for j in jobs]
        for i, f in enumerate(as_completed(futs), 1):
            (d, *_), row = f.result()
            rows.setdefault(str(d), []).append(row)
            if i % 10 == 0 or i == len(jobs):
                save()
                el = time.time() - t0
                print(f"{i}/{len(jobs)}  {el / 60:.1f} min, ~{el / i * (len(jobs) - i) / 60:.0f} min left", flush=True)
    save()
    print("wrote", OUT)


if __name__ == "__main__":
    main()
