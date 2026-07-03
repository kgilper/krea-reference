# Krea 2 V10 Documentation Index

This is the map for the V10 reference-stack nodes and workflows. V10 keeps
everything from V9 and adds four more quick recipes, guide direction
(counter-examples), per-card timing, manual layer dials, balance for hot
stacks, a study cache, and two feedback outputs. The
[V9 index](krea-v9-documentation-index.md) remains the map for the V9 nodes.

![Synthetic reference images included with Krea Reference](../example_assets/krea-reference-examples/contact_sheet.png)

## Start Here

| Resource | Use it for |
| --- | --- |
| [Project README](../README.md) | Product overview, installation, and what V10 adds. |
| [V10 visual HTML guide](krea-v10-user-guide.html) | Rich visual walkthrough of every V10 control. |
| [V10 Markdown guide](krea-v10-user-guide.md) | GitHub-friendly version of the guide. |
| [V10 technical companion](krea-v10-technical-paper.md) | The V10 mechanics: direction math, balance, the study cache, verification, limitations. |
| [V9 technical paper](krea-v9-technical-paper.md) | The shared architecture both versions run on. |
| [Example workflows README](../example_workflows/README.md) | Which workflow to load first and what each one demonstrates. |

## Workflows

| Workflow | Use it for |
| --- | --- |
| [V10 full showcase workflow](../example_workflows/krea-v10-full-showcase-workflow.json) | Best first run. Six cards including the new palette, environment, and framing recipes, per-card timing, gentle balance, and both feedback outputs. |
| [V10 counter-example workflow](../example_workflows/krea-v10-counter-example-workflow.json) | The new `away from this image` direction: keep the subject, push a style out. |
| [V10 starter reference stack workflow](../example_workflows/krea-v10-reference-stack-workflow.json) | Compact graph for building your own V10 reference stack. |

## Node Documentation

| Node | Details |
| --- | --- |
| [KG Krea 2 Image Guide Card V10](nodes/kg-krea-2-image-guide-card-v10.md) | The four new recipes, guide direction, per-card timing, and the manual layer dials. |
| [KG Krea 2 Reference Stack Encoder V10](nodes/kg-krea-2-reference-stack-encoder-v10.md) | Balance, study reuse, the stack report, and the prepared-references output. |
| [Node documentation index](nodes/README.md) | Short index of all included node pages. |

## Demo Journeys

Every demo shows the full journey - input images, recipe and settings, the
exact prompt, and the result - and every PNG below has the matching V10
workflow embedded (drag it into ComfyUI):

![Krea V10 demo output gallery](assets/krea-v10/demos/recipe-gallery.png)

- [suggest-color-palette.png](assets/krea-v10/demos/suggest-color-palette.png) (+ [prompt-only baseline](assets/krea-v10/demos/suggest-color-palette-off.png))
- [use-background-setting.png](assets/krea-v10/demos/use-background-setting.png)
- [copy-camera-framing.png](assets/krea-v10/demos/copy-camera-framing.png)
- [mood-board-only.png](assets/krea-v10/demos/mood-board-only.png)
- [timing-style-early-only.png](assets/krea-v10/demos/timing-style-early-only.png) vs [timing-style-final-only.png](assets/krea-v10/demos/timing-style-final-only.png)
- [counter-example-baseline.png](assets/krea-v10/demos/counter-example-baseline.png) vs [counter-example-toward.png](assets/krea-v10/demos/counter-example-toward.png)
- [full-showcase.png](assets/krea-v10/demos/full-showcase.png)

Per-demo settings: [guide-demo-manifest.json](assets/krea-v10/demos/guide-demo-manifest.json).
Two renders wait for the V10 nodes to reach the render machine: the
away-direction result and a balance comparison (their workflows already
ship). The V9 gallery lives at [assets/krea-v9/demos](assets/krea-v9/demos/).

## Key Benefits

- The four previously manual-only jobs (palette, background/setting, camera
  framing, mood board) are now one-click quick recipes.
- You can write your own recipes: schema-validated YAML/JSON files in
  [custom_recipes/](../custom_recipes/README.md) become first-class
  `Use image for` choices, no code required.
- `Guide direction` turns any card into a counter-example: not this style,
  not this palette, not this subject.
- `When this card guides` gives every card its own timing without touching
  the stack handoff.
- `Balance strong cards` keeps hot multi-card stacks from fighting, and says
  so in the report when it intervenes.
- `Reuse image studies` makes strength/timing tuning re-runs encode-free.
- The stack report and prepared-references outputs replace guesswork with
  feedback: every cap, curve, guard clamp, and encoder pass is narrated.
- The full guard's prompt rewriter understands marking words in Spanish,
  French, German, Portuguese, and Italian.
- V9 and V10 cross-connect through the same `KG_KREA_REFERENCE` link type;
  saved V9 workflows keep working unchanged.

## Recommended Counter-Example Shape

```text
Reference image 1 -> Guide Card V10 (keep the same subject, toward, 0.80) -> Stack V10
Reference image 2 -> Guide Card V10 (suggest the visual style, away, 0.25) -> Stack V10
Stack V10 (conditioning) -> sampler positive input
Stack V10 (stack_report) -> Preview Any
Stack V10 (prepared_references) -> Preview Image
```

Keep away cards at `0.10` to `0.30` and always give the stack something
positive - a written prompt or a toward card - that says what you do want.

## Maintainer Source Touchpoints

- [kg_krea_v10/](../kg_krea_v10) (node classes in `guide_card.py` and `encoder.py`; V10 tables in `recipes.py` and `prompts.py`; the user-recipe loader in `custom_recipes.py`; the study cache, report builder, and contact sheet in `cache.py`, `report.py`, and `preview.py`; V9 locating shim in `_v9.py`)
- [custom_recipes/](../custom_recipes) (user recipe drop folder: README, schema, and the shipped template)
- [kg_krea_v9/](../kg_krea_v9) (shared math and host adapters, unchanged)
- [__init__.py](../__init__.py)
- [web/krea_reference_stack_v9_ui.js](../web/krea_reference_stack_v9_ui.js) (covers both versions)
- [tests/test_krea_v10.py](../tests/test_krea_v10.py)
