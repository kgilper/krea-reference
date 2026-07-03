"""Extract Krea 2's learned per-tap weighting (txtfusion.projector) from a checkpoint.

Reads only the safetensors header + the one small tensor - it does NOT load
the model. Reproduces model_prior.json so the 12 prior values are never a
magic number: rerun against any Krea 2 checkpoint (e.g. a new version, or the
8B) to re-derive the prior for that model.

Usage:
  python extract_model_prior.py --model /path/to/krea2_turbo_bf16.safetensors
  python extract_model_prior.py --model ... --write   # update model_prior.json
"""

import argparse
import array
import json
import struct
from pathlib import Path

HERE = Path(__file__).resolve().parent
TENSOR = "txtfusion.projector.weight"


def read_tensor(path, name):
    with open(path, "rb") as f:
        n = struct.unpack("<Q", f.read(8))[0]
        header = json.loads(f.read(n))
        data_start = 8 + n
        if name not in header:
            raise KeyError("{} not in {} (is this a Krea 2 diffusion model?)".format(name, path))
        meta = header[name]
        start, end = meta["data_offsets"]
        f.seek(data_start + start)
        raw = f.read(end - start)
    dt = meta["dtype"]
    if dt == "BF16":
        u = array.array("H"); u.frombytes(raw)
        vals = [struct.unpack("<f", struct.pack("<I", x << 16))[0] for x in u]
    elif dt == "F32":
        fa = array.array("f"); fa.frombytes(raw); vals = list(fa)
    elif dt == "F16":
        import numpy as np
        vals = np.frombuffer(raw, dtype=np.float16).astype(float).tolist()
    else:
        raise ValueError("unhandled dtype {}".format(dt))
    return vals, dt, meta["shape"]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", required=True, help="path to a krea2 diffusion-model .safetensors")
    ap.add_argument("--write", action="store_true", help="update model_prior.json with the extracted values")
    args = ap.parse_args()

    vals, dt, shape = read_tensor(args.model, TENSOR)
    print("{}  shape={} dtype={}".format(TENSOR, shape, dt))
    print("weights (tap 0..11):", [round(v, 4) for v in vals])
    a = [abs(v) for v in vals]
    tot = sum(a) or 1.0
    print("|weight| share:      ", [round(x / tot, 3) for x in a])
    print("importance ranking:  ", sorted(range(len(vals)), key=lambda i: -a[i]))

    if args.write:
        prior_path = HERE / "model_prior.json"
        prior = json.loads(prior_path.read_text(encoding="utf-8"))
        prior["weights"] = [round(v, 4) for v in vals]
        prior["shape"] = shape
        prior["dtype"] = dt
        prior_path.write_text(json.dumps(prior, indent=2) + "\n", encoding="utf-8")
        print("updated", prior_path)


if __name__ == "__main__":
    main()
