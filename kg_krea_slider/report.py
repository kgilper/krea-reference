"""Plain-language report for the Concept Slider stack.

Same feedback philosophy as the V10 stack report: say what actually
happened (which sliders are live, at what push, from which pole
sentences; which were skipped and why; what the encodes cost), so a
silent or surprising result is explainable without reading code.
"""


def _shorten(text, limit=90):
    text = " ".join(str(text or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _signed(value):
    return "{:+.2f}".format(float(value))


def build_report(info):
    lines = []
    lines.append("KG Concept Slider Stack V1")
    prompt = _shorten(info.get("prompt_text", ""))
    lines.append('prompt: "{}"'.format(prompt) if prompt else "prompt: (empty)")
    lines.append(
        "overall slider reach {:.2f} | encoder passes: {} new, {} reused".format(
            float(info.get("reach", 1.0)),
            int(info.get("encodes_done", 0)),
            int(info.get("reused_studies", 0)),
        )
    )

    sliders = info.get("sliders", [])
    skipped = info.get("skipped", [])
    if not sliders and not skipped:
        lines.append("no sliders connected - prompt encoded as written")

    for slider in sliders:
        lines.append(
            'Slider {} "{}" at {} -> push {}'.format(
                slider.get("index"),
                _shorten(slider.get("description", "") or "(custom poles)", 40),
                _signed(slider.get("value", 0.0)),
                _signed(slider.get("weight", 0.0)),
            )
        )
        lines.append(
            "  increase{}: \"{}\"".format(
                " (auto)" if slider.get("plus_auto") else "",
                _shorten(slider.get("plus_text", "")),
            )
        )
        lines.append(
            "  decrease{}: \"{}\"".format(
                " (auto)" if slider.get("minus_auto") else "",
                _shorten(slider.get("minus_text", "")),
            )
        )

    for skip in skipped:
        lines.append("Slider {} skipped - {}".format(skip.get("index"), skip.get("reason")))

    return "\n".join(lines)
