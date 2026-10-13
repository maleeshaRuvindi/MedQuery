import atexit, sys
from importlib.metadata import packages_distributions, version

def report():
    stdlib = sys.stdlib_module_names          # Python 3.10+
    mod_to_dists = packages_distributions()   # e.g. {'cv2': ['opencv-python']}
    used = {}
    for name in list(sys.modules):
        top = name.split(".")[0]
        if top in stdlib or top.startswith("_"):
            continue
        for dist in mod_to_dists.get(top, []):
            used[dist] = version(dist)
    with open("runtime_requirements.txt", "w") as f:
        for dist, ver in sorted(used.items(), key=lambda x: x[0].lower()):
            f.write(f"{dist}=={ver}\n")

atexit.register(report)