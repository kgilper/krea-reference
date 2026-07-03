# Scoring the deepstack sweep

After `generate_sweep.py --server ...` renders the grid, score every spike
render **against the control** (`<ref>__sweep-control.png`) to determine what
each chunk carries. The control and the spike share prompt, seed, reference,
strength, pooled channel, and all other chunks - so any visible difference is
attributable to the spiked chunk alone.

## Procedure

For each reference (`subject`, `palette`) and each chunk `L`:

1. Open `<ref>__sweep-control.png` and `<ref>__sweep-chunk-LL-gain-4.png`
   side by side.
2. Judge which single aspect changed **most** relative to the control, and how
   strongly (none / subtle / clear / dominant):

   | Aspect | What to look for |
   | --- | --- |
   | structure | subject shape, pose, layout, spatial composition shifting toward the reference |
   | palette | overall color cast, hue relationships moving toward the reference |
   | texture | surface/material grain, finish, micro-detail |
   | lighting | light direction, contrast, glow, shadow, mood |
   | (none) | no meaningful change from control |

3. Record: `chunk L -> <aspect> (<strength>)`. If two aspects move together,
   record both with the dominant one first.

## Recording

Fill the verdict table in [README.md](README.md) - one row per chunk, with the
verdict from each reference and a consensus column. A determination is
"solidified" when:

- both references agree on each chunk's dominant aspect, and
- the measured structure->transition->appearance ordering matches the
  convergent-table prediction (chunks 0-4 structure, 5-6 transition, 7/8/10
  appearance with 8 strongest), OR any disagreement is documented with its
  consequence for the tables.

If a scoring pass is done by an agent, have a second independent agent score
the same grid blind and reconcile; note both in the record.

## Optional: multi-level confirmation

Re-run with `--gains 2 4 6` to confirm each chunk's response is monotonic in
gain (a real carrier gets stronger with a bigger spike; noise does not). Note
the gain at which each chunk's effect first becomes clearly visible.
