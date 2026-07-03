# KG Krea 2 Reference Stack Encoder V10

Class: `KGTextEncodeKreaImageReferencesV10`  
Node key: `KGTextEncodeKreaImageReferencesV10`  
Category: `advanced/conditioning`  
Source: `kg_krea_v10/encoder.py`  
Deep dive: [V10 technical reference](../krea-v10-technical-paper.md) (standalone - every widget, the delta architecture, and all the math)

## What It Does

Combines the final prompt and up to 12 guide cards (V10 or V9) into Krea conditioning, exactly like the [V9 stack](kg-krea-2-reference-stack-encoder-v9.md), and adds: counter-example handling for away cards, an optional balance budget for hot stacks, a content-keyed study cache that makes strength tuning compose-only, and two feedback outputs.

## Everything The V9 Stack Has

The first nine rows repeat the V9 stack exactly: prompt, prompt strength, slider feel, detail level, framing, timing, handoff, and the text/logo guard prompt handling behave identically. The text/logo guard's prompt rewriter additionally understands common marking words in Spanish, French, German, Portuguese, and Italian.

## New Controls

### `Balance strong cards`

Several simultaneously strong cards blend less faithfully than the same cards used separately (first-order composition). This choice puts a per-phase budget on the summed departure from neutral and softly scales every card down when the stack exceeds it:

- `off - use my values`: exact V9 behavior; your values are used as set.
- `gentle balance`: budget `2.5`. Rarely intervenes; catches genuinely hot stacks.
- `strict balance`: budget `1.5`. Keeps multi-card blends conservative.

The written prompt is never balanced; only image cards are scaled. The stack report states the applied scale whenever balancing intervenes.

### `Reuse image studies`

Ingredient studies (the base encode and each image's isolated delta) depend only on the prompt and the prepared images, never on strengths, timing, or balance. This choice caches them:

- `reuse between runs - faster tuning`: re-runs that change only strengths, direction, timing, handoff, or balance reuse every study and skip all encoder passes. Keys are content fingerprints, so editing an image or the prompt re-studies automatically.
- `always re-study`: exact V9 behavior; every run pays full encode cost.

Reuse assumes the connected CLIP is unchanged between runs (it is validated by object identity). Pick `always re-study` while hot-swapping CLIP patches or LoRA hooks.

## Outputs

- `conditioning`: Krea conditioning for the KSampler positive input (same as V9).
- `stack_report`: a plain-language account of the run. Per card: what was requested, what it actually got, and why (feel curve, recipe cap, text/logo guard); the card's recipe `focus` when set; plus prompt handling notes, balance decisions, timing, encoder pass counts, and skipped cards. Wire it into any text-display node when a card seems to be doing nothing.
- `prepared_references`: a contact sheet of exactly what the vision encoder studied after framing, washes, color, and detail reduction, one frame per active card. Wire it into a Preview Image node to see what survived preparation - if a style card still shows a recognizable subject, lower its detail or strengthen its treatment.

## Performance

Same linear model as V9 (one extra encoder pass per non-neutral card, plus one when prompt strength is not 1.0), except cache hits: a re-run with only strength/timing/balance changes costs zero encoder passes. The report prints the exact pass count each run.
