# Recipe Lab - rapid tweak-and-test for Krea recipes

A small harness for iterating on recipe settings against the real Krea 2 model
fast, using a **mixture of agent tiers**: cheap agents do the mechanical
rendering; a stronger model judges whether the result achieves the recipe's
intent. It turns "change a number, guess if it's better" into "change a
number, render it, and get a scored verdict from images."

## Pieces

| File | Role | Who runs it |
| --- | --- | --- |
| [tweak_test.py](tweak_test.py) | Render engine: given a recipe (built-in label or a full tweak bundle) + reference + prompt + strength + seed, renders on the ComfyUI box and prints `{name, image, metrics}` as JSON. Pure mechanical work, no judgment. | a cheap agent (Haiku), or you directly |
| [style_transfer_stack_test.py](style_transfer_stack_test.py) | Multi-card V10 style-transfer harness: content anchor + style reference + optional away-layout guard. Used to test the repeatable style-transfer method in [v10-style-transfer-method.md](v10-style-transfer-method.md). | maintainer |
| [style_transfer_reliability_suite.py](style_transfer_reliability_suite.py) | Fixed V10 style-transfer regression matrix: six content/style stress cases across the default and leak-control methods, with JSONL metrics and a contact sheet. | maintainer |
| [style_transfer_seed_sweep.py](style_transfer_seed_sweep.py) | Seed-stability check for the recommended V10 style-transfer methods: three stress cases, two methods, three seeds each, with JSONL metrics and a contact sheet. | maintainer |
| the `recipe-tweak-test` workflow | Orchestrates: for each recipe, Haiku agents render the current settings + candidate tweaks in parallel, then a Fable agent **reads the images and scores** each against the recipe's stated intent, names the best, and recommends a change. | the Workflow tool |
| [generate_guide_demos.py](generate_guide_demos.py) | Renders the V10 user-guide demo set (every recipe + the journeys) with the matching drag-in V10 workflow embedded in each PNG, and rebuilds the guide manifest + recipe-gallery contact sheet in `docs/assets/krea-v10/demos/`. `--only <slugs>` re-renders a subset; `--skip-render` rebuilds manifest/sheet only. | maintainer |
| refs/ | Local copies of reference images so the judge agent can see them. | - |
| runs/ | Local copies of every rendered variant (also saved on the box under `output/claude-generations/recipe-lab/`). | - |

Gotcha: dropping a brand-new custom recipe label onto the box races
ComfyUI's node-definition cache - the first `/prompt` after the drop can 400.
Retry once (or hit `/object_info/KGKrea2ImageGuideCardV10` first to force a
refresh).

## The loop

1. **Define the job**: the recipe label, its *intent* in one sentence (what it
   should do and what it must NOT overstep), a reference image, a content
   prompt, and a list of variants to compare (the current recipe plus any
   tweaks - a tweak is a full recipe bundle, e.g. a different `layers` array or
   `global`).
2. **Render (cheap)**: one Haiku agent per variant runs `tweak_test.py`. Renders
   serialize on the single GPU but the agent orchestration is free.
3. **Judge (capable)**: one Fable agent Reads all the variant images + the
   reference and scores them 0-10 against the intent, picks the best, and
   recommends a concrete settings change if the current recipe underperforms.
4. **Act**: apply the winning/recommended settings, re-run to confirm, commit.

## Run it

Directly (one render):

```bash
python docs/recipe-lab/tweak_test.py --builtin "suggest the visual style" \
  --ref layerprobe2/base.png --prompt "a plain white bowl on a wooden table" \
  --strength 0.6 --seed 424242 --name style-current
```

As the judged workflow: invoke the `recipe-tweak-test` workflow (it embeds a
demo job set; pass `args.jobs` to test your own recipes/tweaks). Cheap agents
render, Fable judges, and the run returns per-recipe verdicts.

## Requirements

- The ComfyUI box (default `http://10.0.0.35:8188`) with the V10 nodes
  installed and the reference images in its `input/` folder.
- Renders and reference copies go to the dedicated `claude-generations/` output
  folder; the harness only reads back what it generated.

Maintainer tooling - lives under `docs/` (excluded from registry packs).
