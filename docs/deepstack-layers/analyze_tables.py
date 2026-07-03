"""Show the designed shape of the layer-gain tables (no rendering).

Prints the five built-in tables from the live code so their structure is
visible: appearance roles suppress the shallow taps (0-4) and spike the deep
ones (7/8/10, strongest at 8).

IMPORTANT - what this does and does NOT show. The four appearance tables are
per-role scalings of ONE borrowed spike template (adopted from the
ComfyUI-ConditioningKrea2Rebalance node; see README section 2). So their
agreement is *design self-consistency*, NOT four independent measurements
converging - do not read it as empirical confirmation of each tap's function.
The honest per-tap measurement is the single-chunk sweep (generate_sweep.py),
which has not been run. This script just makes the designed pattern legible.

Run: python docs/deepstack-layers/analyze_tables.py
Reads the live tables from kg_krea_v9/recipes.py via the test stubs, so the
output tracks the code and can never silently drift from it.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tests"))

from _kg_stub_env import load_module  # noqa: E402

CHUNKS = 12
# The four tables whose job is to import appearance and reject structure.
# Their agreement is the evidence; the even baseline is the neutral control.
APPEARANCE = ("style", "palette", "material", "lighting")


def load_tables():
    v9, _ = load_module("kg_krea_v9", "kg_deepstack_table_analysis")
    r = v9.recipes
    return {
        "even": list(r.EVEN_LAYER_PULL),
        "style": list(r.STYLE_LAYER_PULL),
        "palette": list(r.PALETTE_LAYER_PULL),
        "material": list(r.MATERIAL_LAYER_PULL),
        "lighting": list(r.LIGHTING_LAYER_PULL),
    }


def classify(chunk_vals):
    """Consensus verdict for one chunk across the appearance tables."""
    lo, hi = min(chunk_vals), max(chunk_vals)
    mean = sum(chunk_vals) / len(chunk_vals)
    if hi < 1.0:
        return mean, "STRUCTURE (all suppress <1.0)"
    if all(abs(v - 1.0) < 1e-9 for v in chunk_vals):
        return mean, "TRANSITION (all neutral)"
    if lo >= 1.0 and mean > 1.5:
        return mean, "APPEARANCE (all spike >1.0)"
    if lo >= 1.0:
        return mean, "mild-positive (all >=1.0, gentle)"
    return mean, "mixed"


def main():
    tables = load_tables()

    print("=" * 78)
    print("Per-chunk gains across the five tuned tables")
    print("=" * 78)
    print("chunk | " + " ".join(f"{n:>8}" for n in tables))
    for i in range(CHUNKS):
        print(f"  {i:>2}  | " + " ".join(f"{tables[n][i]:>8.2f}" for n in tables))

    print("\n" + "=" * 78)
    print("Consensus of the four appearance tables (style/palette/material/lighting)")
    print("=" * 78)
    print("chunk |  mean | min  | max  | consensus verdict")
    verdicts = []
    for i in range(CHUNKS):
        vals = [tables[n][i] for n in APPEARANCE]
        mean, verdict = classify(vals)
        verdicts.append((i, mean, verdict))
        print(f"  {i:>2}  | {mean:>5.2f} | {min(vals):.2f} | {max(vals):.2f} | {verdict}")

    print("\n" + "=" * 78)
    print("Findings")
    print("=" * 78)
    structure = [i for i, _, v in verdicts if v.startswith("STRUCTURE")]
    appearance = [i for i, _, v in verdicts if v.startswith("APPEARANCE")]
    ranked = sorted(appearance, key=lambda i: -sum(tables[n][i] for n in APPEARANCE))
    print(f"  Structure-carrying chunks (all 4 suppress): {structure}")
    print(f"  Appearance-carrying chunks (all 4 spike):    {appearance}")
    print("  Appearance response ranking (strongest first):")
    for rank, i in enumerate(ranked, 1):
        m = sum(tables[n][i] for n in APPEARANCE) / len(APPEARANCE)
        print(f"    #{rank}  chunk {i:>2}  mean {m:.2f}x")

    # Monotonic front ramp = structure fades in smoothly with depth 0->5.
    print("  Front-ramp monotonicity (chunks 0-5, structure fading in with depth):")
    for n in APPEARANCE:
        front = tables[n][:6]
        mono = all(front[j] <= front[j + 1] for j in range(5))
        print(f"    {n:>8}: {front}  monotonic-rising={mono}")

    print("\n  Interpretation: the tables encode a DESIGN - shallow taps (0-4) turned")
    print("  down, deep taps (7/8/10) spiked, strongest at 8 - shared across roles")
    print("  because they scale one borrowed template. This is a self-consistent,")
    print("  principled design, NOT a per-tap measurement. Measure with generate_sweep.py.")


if __name__ == "__main__":
    main()
