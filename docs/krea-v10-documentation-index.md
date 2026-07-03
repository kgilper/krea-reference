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

## Recipe Demo Images

The V9 demo gallery lives at [assets/krea-v9/demos](assets/krea-v9/demos/).
V10 demo renders with embedded workflows (matching the V9 gallery format,
covering the four new recipes, direction, and timing) are produced on a live
Krea 2 ComfyUI as part of the V10 release checklist and will land under
`assets/krea-v10/demos/`.

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
