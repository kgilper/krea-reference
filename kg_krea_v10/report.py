"""Plain-language stack report for the V10 encoder.

The V9 nodes decide a lot on the artist's behalf (feel curves, caps, guard
clamps, phase multipliers) and say nothing. The V10 stack narrates those
decisions per run: what each card requested, what it actually got and why,
what the prompt side did, and what the run cost in encoder passes.
"""


def _fmt(value):
    return "{:.2f}".format(float(value))


def _prompt_line(info):
    text = str(info.get("prompt_text", "")).strip().replace("\n", " ")
    if len(text) > 100:
        text = text[:97] + "..."
    return 'Prompt: "{}" at strength {}.'.format(text, _fmt(info.get("prompt_strength", 1.0)))


def _timing_line(info):
    line = "Timing: {}.".format(info.get("timing_label", "smart per-card timing"))
    if info.get("two_phase"):
        line = line[:-1] + " with early-to-final handoff at {}.".format(_fmt(info.get("split", 0.4)))
    return line


def _balance_lines(info):
    label = info.get("balance_label", "off - use my values")
    if info.get("balance_budget") is None:
        return ["Balance: off - card values used exactly as set."]
    lines = []
    scales = info.get("balance_scales", [])
    phase_names = ["early phase", "final phase"] if len(scales) == 2 else ["whole image"]
    scaled_any = False
    for name, scale in zip(phase_names, scales):
        if scale < 1.0:
            lines.append(
                "Balance: {} scaled strong cards to {}x of their departure ({}).".format(label, _fmt(scale), name)
            )
            scaled_any = True
    if not scaled_any:
        lines.append("Balance: {} - cards were within budget, nothing scaled.".format(label))
    return lines


def _studies_line(info):
    if not info.get("reuse", False):
        return "Studies: {} encoder passes this run (reuse off - everything re-studied).".format(
            info.get("encodes_done", 0)
        )
    reused = info.get("reused_studies", 0)
    if reused:
        return "Studies: {} encoder passes this run; reused {} cached studies from earlier runs.".format(
            info.get("encodes_done", 0), reused
        )
    return "Studies: {} encoder passes this run; studies cached for faster strength tuning.".format(
        info.get("encodes_done", 0)
    )


def _card_line(card, two_phase):
    parts = ["Card {} ({}".format(card["index"], card.get("purpose", "hand-built packet"))]
    if card.get("direction") == "away":
        parts[0] += ", away from this image"
    parts[0] += "):"

    requested = float(card.get("requested", 0.0))
    packet_strength = float(card.get("packet_strength", requested))
    effective = float(card.get("effective", packet_strength))

    if card.get("cap") is not None and requested > float(card["cap"]) + 1e-9:
        parts.append(
            "requested {} -> capped at {} by {}.".format(
                _fmt(requested),
                _fmt(card["cap"]),
                "the text/logo guard" if card.get("guard") else "the recipe's strength cap",
            )
        )
    elif abs(effective - requested) > 0.005:
        parts.append(
            "requested {} -> guiding at {} after the slider feel curve.".format(_fmt(requested), _fmt(effective))
        )
    else:
        parts.append("guiding at {}.".format(_fmt(effective)))

    targets = card.get("targets", [])
    if targets:
        if two_phase and len(targets) == 2:
            parts.append(
                "Targets: early shape {}x / look {}x, final shape {}x / look {}x.".format(
                    _fmt(targets[0][0]), _fmt(targets[0][1]), _fmt(targets[1][0]), _fmt(targets[1][1])
                )
            )
        else:
            parts.append("Targets: shape {}x / look {}x.".format(_fmt(targets[0][0]), _fmt(targets[0][1])))

    if card.get("timing") not in (None, "recipe"):
        timing_words = {
            "constant": "guides the whole image",
            "early": "guides early layout only",
            "late": "guides final details only",
        }
        parts.append("Timing: {}.".format(timing_words.get(card["timing"], card["timing"])))

    return " ".join(parts)


def build_report(info):
    """Assemble the full plain-language report string."""
    lines = ["KG Krea 2 Reference Stack Encoder V10 - stack report"]

    lines.append(_prompt_line(info))
    for note in info.get("prompt_notes", []):
        lines.append("  - {}".format(note))

    lines.append(_timing_line(info))
    lines.extend(_balance_lines(info))
    lines.append(_studies_line(info))

    cards = info.get("cards", [])
    if cards:
        lines.append("")
        for card in cards:
            lines.append(_card_line(card, info.get("two_phase", False)))
    else:
        lines.append("")
        lines.append("No reference cards active - prompt-only conditioning.")

    skipped = info.get("skipped", [])
    if skipped:
        reasons = ", ".join("card {} ({})".format(s["index"], s["reason"]) for s in skipped)
        lines.append("Skipped without cost: {}.".format(reasons))

    if info.get("blank_surface_guard"):
        lines.append("Text/logo guard active: guarded cards are clamped to blank-surface behavior.")

    if info.get("layer_fallback"):
        lines.append(
            "Note: this model's conditioning width did not split into 12 layer chunks; "
            "layer-targeted recipes fell back to broad guidance."
        )

    return "\n".join(lines)
