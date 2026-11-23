import json, warnings
warnings.filterwarnings("ignore")
from concurrent.futures import ProcessPoolExecutor
from search_catalog import score
if __name__ == "__main__":
    cands = [{"ch": ch, "t": t, "t_hook": 16} for ch in (5, 7, 9, 11) for t in (10, 12, 14)]
    with ProcessPoolExecutor(5) as ex:
        res = list(ex.map(score, [("bone", c) for c in cands]))
    for c, r in zip(cands, res):
        print(c, round(r.get("mass", 0), 1), round(r.get("kg", 0), 1), flush=True)
    best = min(zip(cands, res), key=lambda cr: cr[1]["obj"])
    json.dump({"bone": {"best": best[0], "result": best[1]}}, open("out/bone_sized.json", "w"), indent=1, default=float)
    print("BEST", best[0], best[1]["mass"], best[1]["kg"], flush=True)
