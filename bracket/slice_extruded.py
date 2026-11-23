import json, subprocess, warnings, re
warnings.filterwarnings("ignore")
from extruded import DESIGNS, W
from make_catalog import to_part
from build123d import export_stl
res = json.load(open("out/extruded_sized.json"))
PS = r"C:\Program Files\Prusa3D\PrusaSlicer\prusa-slicer-console.exe"
for name, v in res.items():
    geom = DESIGNS[name][0](**v["best"])
    stl = f"out/print/shelf_{name}.stl"
    export_stl(to_part(geom, W, W), stl)
    tmf = f"out/print/shelf_{name}.3mf"
    subprocess.run(["uv", "run", "python", "../tools/make_3mf.py", tmf, "../tools/prusa/cfg_extruded.ini", f"{stl}:1"], check=True, capture_output=True)
    subprocess.run([PS, "--dont-arrange", "--binary-gcode=0", "--export-gcode", tmf, "-o", "out/print/tmp.gcode"], check=True, capture_output=True)
    g = open("out/print/tmp.gcode").read()
    grams = float(re.search(r"filament used \[g\] = ([\d.]+)", g).group(1))
    t = re.search(r"estimated printing time \(normal mode\) = (.+)", g).group(1)
    r = v["result"]
    print(f"{name:15s} sliced {grams:6.1f} g, {t:>10s} | FEA solid-eq {r['mass']:.0f} g, safe {r['kg']:.1f} kg | {v['best']}", flush=True)
