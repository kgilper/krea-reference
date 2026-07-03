"""Stage 0: how far are the shipped tables from the model's own tap emphasis?

Compares each built-in layer table against Krea 2's learned per-tap weighting
(txtfusion.projector, model_prior.json). This is the cheapest, no-render check
in the derivation methodology (README section 4): if a table's emphasis does
not track the taps the model actually relies on, that is a flag the table may
be suboptimal.

Honest scope: the projector weights the PROCESSED taps (after per-tap blocks)
while the node's gains act on the RAW tap delta (before them), so perfect
alignment is not expected and misalignment is a smell test, not proof. It
tells you where to look, and gives a model-informed starting point for the
real derivation (Stages 1-3).

Run: python docs/deepstack-layers/compare_to_model_prior.py
"""

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
sys.path.insert(0, str(REPO_ROOT / "tests"))

from _kg_stub_env import load_module  # noqa: E402

APPEARANCE = ("style", "palette", "material", "lighting")


def load_tables():
    v9, _ = load_module("kg_krea_v9", "kg_prior_compare")
    r = v9.recipes
    return {
        "even": list(r.EVEN_LAYER_PULL), "style": list(r.STYLE_LAYER_PULL),
        "palette": list(r.PALETTE_LAYER_PULL), "material": list(r.MATERIAL_LAYER_PULL),
        "lighting": list(r.LIGHTING_LAYER_PULL),
    }


def ranks(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    rk = [0.0] * len(xs)
    i = 0
    while i < len(xs):
        j = i
        while j + 1 < len(xs) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = sum(range(i, j + 1)) / (j - i + 1)
        for k in range(i, j + 1):
            rk[order[k]] = avg
        i = j + 1
    return rk


def pearson(a, b):
    n = len(a)
    ma, mb = sum(a) / n, sum(b) / n
    cov = sum((a[i] - ma) * (b[i] - mb) for i in range(n))
    va = sum((x - ma) ** 2 for x in a) ** 0.5
    vb = sum((x - mb) ** 2 for x in b) ** 0.5
    return cov / (va * vb) if va and vb else 0.0


def spearman(a, b):
    return pearson(ranks(a), ranks(b))


def main():
    prior = json.loads((HERE / "model_prior.json").read_text(encoding="utf-8"))
    w = prior["weights"]
    importance = [abs(x) for x in w]
    tot = sum(importance) or 1.0
    share = [x / tot for x in importance]
    tables = load_tables()

    print("=" * 74)
    print("Model's own per-tap emphasis (|txtfusion.projector|, normalized)")
    print("=" * 74)
    print("tap:   " + " ".join("{:>5}".format(i) for i in range(12)))
    print("share: " + " ".join("{:>5.3f}".format(s) for s in share))
    print("model ranking (most-used first):", sorted(range(12), key=lambda i: -importance[i]))

    print("\n" + "=" * 74)
    print("Table emphasis vs. the model prior (rank correlation; 1.0 = aligned)")
    print("=" * 74)
    for name in APPEARANCE:
        table = tables[name]
        rho = spearman(table, importance)
        # Where the table and the model most disagree.
        table_rank = {t: r for t, r in zip(range(12), ranks([-x for x in table]))}
        model_rank = {t: r for t, r in zip(range(12), ranks([-x for x in importance]))}
        gaps = sorted(range(12), key=lambda i: -abs(table_rank[i] - model_rank[i]))
        worst = ["tap {} (table#{}/model#{})".format(i, int(table_rank[i]) + 1, int(model_rank[i]) + 1) for i in gaps[:3]]
        print("  {:>8}: rank-corr {:+.2f}   biggest gaps: {}".format(name, rho, "; ".join(worst)))

    print("\n" + "=" * 74)
    print("Model-informed starting shape (for Stages 1-3, NOT a drop-in table)")
    print("=" * 74)
    # A neutral illustration: gains that track the model's emphasis, scaled so
    # the mean is ~1 (so it is comparable to the even baseline before role tuning).
    mean_share = sum(share) / 12
    prior_shape = [round(s / mean_share, 2) for s in share]
    print("  gains proportional to model tap-use:", prior_shape)
    style = tables["style"]
    print("  STYLE table spikes taps 7/8/10 = {}/{}/{} (biggest at 8);".format(style[7], style[8], style[10]))
    print("  the model leans hardest on taps {} (biggest at 7) - different taps.".format(
        sorted(range(12), key=lambda i: -importance[i])[:3]))
    print("  reminder: this is a prior/sanity-check, not a drop-in table. Derive real")
    print("  gains with the selectivity harness + optimization (README section 4).")


if __name__ == "__main__":
    main()
