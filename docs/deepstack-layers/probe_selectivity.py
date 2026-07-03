"""Stage 1: measure each of Krea 2's 12 text-layer taps for attribute selectivity.

Consumes the per-tap conditioning signatures saved by the KG Conditioning
Probe node (probe_node/) over a CONTROLLED set of reference images, and
computes - offline, no rendering - a tap x attribute selectivity matrix:
for each tap, how much of its contribution is explained by palette vs.
structure vs. texture vs. lighting.

Method (multivariate eta-squared / variance decomposition):
  delta_i(ref) = tap_i signature of (prompt+ref) minus tap_i of the baseline.
  For each tap i and attribute A (a categorical label per reference):
    eta2(i, A) = SS_between(A) / SS_total   in [0, 1]
  where SS uses squared distances between per-ref delta vectors and group
  means. A tap with high eta2 for palette and low for subject is
  palette-selective. This is only interpretable if the reference set is a
  CONTROLLED design (each attribute varied across levels, others balanced) -
  see README section 5 for how to build the sets.

Run:
  python probe_selectivity.py --selftest                       # validate the math (no data needed)
  python probe_selectivity.py --probes <dir> --manifest <json> # analyze real probe output
"""

import argparse
import json
import sys
from pathlib import Path

LAYER_COUNT = 12


# -- vector helpers (pure python; runs anywhere) ---------------------------

def vsub(a, b):
    return [x - y for x, y in zip(a, b)]


def vadd(a, b):
    return [x + y for x, y in zip(a, b)]


def vscale(a, s):
    return [x * s for x in a]


def sq_dist(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b))


def vmean(vectors):
    n = len(vectors)
    out = [0.0] * len(vectors[0])
    for v in vectors:
        for i, x in enumerate(v):
            out[i] += x
    return [x / n for x in out]


# -- core selectivity ------------------------------------------------------

def eta_squared(vectors, levels):
    """Fraction of variance in `vectors` explained by categorical `levels`."""
    grand = vmean(vectors)
    ss_total = sum(sq_dist(v, grand) for v in vectors)
    if ss_total <= 1e-12:
        return 0.0
    groups = {}
    for v, lvl in zip(vectors, levels):
        groups.setdefault(lvl, []).append(v)
    ss_between = 0.0
    for members in groups.values():
        gm = vmean(members)
        ss_between += len(members) * sq_dist(gm, grand)
    return ss_between / ss_total


def selectivity_matrix(deltas_by_ref, attrs_by_ref, attributes):
    """deltas_by_ref: {ref: [tap0_vec, ... tap11_vec]}. Returns eta2[tap][attr]."""
    refs = list(deltas_by_ref)
    matrix = []
    for tap in range(LAYER_COUNT):
        row = {}
        vectors = [deltas_by_ref[r][tap] for r in refs]
        for attr in attributes:
            levels = [attrs_by_ref[r][attr] for r in refs]
            row[attr] = eta_squared(vectors, levels)
        matrix.append(row)
    return matrix, refs


def report(matrix, attributes):
    print("tap | " + " | ".join("{:>9}".format(a) for a in attributes) + " | dominant")
    print("-" * (6 + 12 * len(attributes) + 12))
    for tap in range(LAYER_COUNT):
        row = matrix[tap]
        dom = max(attributes, key=lambda a: row[a])
        cells = " | ".join("{:>9.2f}".format(row[a]) for a in attributes)
        print(" {:>2} | {} | {}".format(tap, cells, dom if row[dom] > 0.15 else "(none)"))
    print("\nPer-attribute tap ranking (most selective first):")
    for attr in attributes:
        ranked = sorted(range(LAYER_COUNT), key=lambda t: -matrix[t][attr])
        print("  {:>9}: {}".format(attr, ranked))


# -- loading real probe output ---------------------------------------------

def load_deltas(probe_dir, manifest):
    """manifest: {"baseline": "<label>", "references": {ref_label: {attr: level}}}."""
    probe_dir = Path(probe_dir)

    def taps(label):
        rec = json.loads((probe_dir / (label + ".json")).read_text(encoding="utf-8"))
        if not rec.get("divides_by_12"):
            raise SystemExit("probe {}: feature width {} does not split into 12 taps".format(
                label, rec.get("feature_width")))
        return rec["tap_mean_vectors"]

    base = taps(manifest["baseline"])
    deltas, attrs = {}, {}
    for ref, ref_attrs in manifest["references"].items():
        ref_taps = taps(ref)
        deltas[ref] = [vsub(ref_taps[i], base[i]) for i in range(LAYER_COUNT)]
        attrs[ref] = ref_attrs
    return deltas, attrs


# -- self-test: fabricate a controlled set with KNOWN selectivity ----------

def selftest():
    """Inject a known tap->attribute map and confirm the analysis recovers it."""
    # Assign each tap a true attribute (mirrors the design hypothesis).
    truth = {0: "structure", 1: "structure", 2: "structure", 3: "structure",
             4: "structure", 5: "structure", 6: "texture", 7: "palette",
             8: "palette", 9: "lighting", 10: "palette", 11: "lighting"}
    attributes = ["palette", "structure", "texture", "lighting"]
    tap_dim = 6
    # A small factorial design: 3 levels per attribute, others held at level 0
    # across four controlled series (one per attribute).
    refs, attrs_by_ref = [], {}
    for attr in attributes:
        for level in range(3):
            name = "{}_{}".format(attr, level)
            refs.append(name)
            a = {x: 0 for x in attributes}
            a[attr] = level
            attrs_by_ref[name] = a

    # Deterministic pseudo-signal (no RNG): each tap responds only to its true
    # attribute's level, plus a tiny fixed per-tap offset.
    def signal(tap, attr_levels):
        lvl = attr_levels[truth[tap]]
        base = [(tap + 1) * 0.01 * (d + 1) for d in range(tap_dim)]
        drive = [lvl * (0.5 + 0.1 * d) for d in range(tap_dim)]
        return vadd(base, drive)

    deltas_by_ref = {r: [signal(t, attrs_by_ref[r]) for t in range(LAYER_COUNT)] for r in refs}
    matrix, _ = selectivity_matrix(deltas_by_ref, attrs_by_ref, attributes)

    ok = True
    for tap in range(LAYER_COUNT):
        dominant = max(attributes, key=lambda a: matrix[tap][a])
        if dominant != truth[tap]:
            ok = False
            print("  MISMATCH tap {}: recovered {}, injected {}".format(tap, dominant, truth[tap]))
    print("Self-test: analysis recovered every injected tap->attribute mapping." if ok
          else "Self-test FAILED.")
    report(matrix, attributes)
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--selftest", action="store_true", help="validate the math on synthetic data")
    ap.add_argument("--probes", help="folder of KG Conditioning Probe .json outputs")
    ap.add_argument("--manifest", help="json: {baseline, references:{ref:{attr:level}}}")
    args = ap.parse_args()

    if args.selftest:
        return selftest()
    if not (args.probes and args.manifest):
        print("need --probes and --manifest (or --selftest). See README section 5.")
        return 2
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    attributes = manifest.get("attributes", ["palette", "structure", "texture", "lighting"])
    deltas, attrs = load_deltas(args.probes, manifest)
    matrix, refs = selectivity_matrix(deltas, attrs, attributes)
    print("Measured tap x attribute selectivity ({} references):\n".format(len(refs)))
    report(matrix, attributes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
