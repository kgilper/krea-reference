"""V10 prompt construction: direction-aware roles and a wider guard net.

Adds counter-example ("away from this image") instruction language on top
of the V9 role instructions, and extends the text/logo guard's marking-word
rewriter with a starter vocabulary for five Latin-script languages
(Spanish, French, German, Portuguese, Italian). The V9 sanitizer still runs
last, so all V9 English behavior is preserved.
"""

import re

from ._v9 import v9

_v9_prompts = v9.prompts

# Re-exported V9 tables and helpers used unchanged by V10.
ROLE_INSTRUCTIONS = _v9_prompts.ROLE_INSTRUCTIONS
SUBJECT_POLICY_INSTRUCTIONS = _v9_prompts.SUBJECT_POLICY_INSTRUCTIONS
blank_surface_positive = _v9_prompts.blank_surface_positive
text_logo_guard_suffix = _v9_prompts.text_logo_guard_suffix
llama_template = _v9_prompts.llama_template
image_pad_prefix = _v9_prompts.image_pad_prefix

# Counter-example phrasing per role for cards set to "away from this image".
# The image's delta is re-added negatively by the encoder; this language
# keeps the prompt side pointed the same direction.
REPEL_ROLE_INSTRUCTIONS = {
    "balanced": "treat as a counter-example; steer the overall result away from this image's look",
    "style": "treat as a style counter-example; steer palette, tonal feel, medium, and rendering finish away from this image",
    "palette": "treat as a palette counter-example; steer the color palette and tonal relationships away from this image",
    "composition": "treat as a layout counter-example; steer pose, placement, camera angle, and scene structure away from this image",
    "framing": "treat as a framing counter-example; steer camera distance, crop, and viewpoint away from this image",
    "identity": "treat as a subject counter-example; keep this image's subject, product, or object design out of the result",
    "environment": "treat as an environment counter-example; steer background, location, and scene context away from this image",
    "lighting": "treat as a lighting counter-example; steer light direction, contrast, mood, and color cast away from this image",
    "material": "treat as a material counter-example; steer surface quality and finish away from this image",
    "loose": "treat as a loose counter-example; gently steer the overall mood away from this image",
    "shape only": "treat as a shape counter-example; steer silhouette and geometric structure away from this image",
    "text/logo safe": ROLE_INSTRUCTIONS["text/logo safe"],
}


def role_system_prompt(refs, blank_surface_guard):
    """V9's role system prompt, with counter-example lines for away cards."""
    if blank_surface_guard and refs and all(ref["role"] == "text/logo safe" for ref in refs):
        return blank_surface_positive()

    if blank_surface_guard:
        lines = [
            "Use broad visual shape, placement, color, and material from each image input.",
            "Marked areas become smooth empty blank surfaces.",
            "Use clean plain undecorated unmarked surfaces.",
        ]
    else:
        lines = [
            "Use the connected image inputs as controlled visual ingredients.",
            "Generate a new image that meets the user's requirements without rendering instruction labels, source labels, captions, or prompt wording.",
        ]
    for i, ref in enumerate(refs, start=1):
        role = ref["role"]
        direction = ref.get("direction", "toward")
        subject_policy = ref.get("subject_policy", "recipe")
        focus = str(ref.get("focus") or "").strip()
        if blank_surface_guard and role == "text/logo safe":
            lines.append("Input {}: blank panel shape only, smooth empty interior.".format(i))
            continue
        if direction == "away":
            instruction = REPEL_ROLE_INSTRUCTIONS.get(role, REPEL_ROLE_INSTRUCTIONS["balanced"])
            lines.append("Input {} role: {}.".format(i, instruction))
            if focus:
                lines.append("Input {} focus: only {} from this image; its other aspects do not apply.".format(i, focus))
            continue
        lines.append("Input {} role: {}.".format(i, ROLE_INSTRUCTIONS.get(role, ROLE_INSTRUCTIONS["balanced"])))
        if focus:
            lines.append(
                "Input {} focus: study only {} from this image; ignore everything else about it.".format(i, focus)
            )
        policy_text = SUBJECT_POLICY_INSTRUCTIONS.get(subject_policy)
        if policy_text and subject_policy != "recipe":
            lines.append("Input {} subject rule: {}.".format(i, policy_text))
    if blank_surface_guard:
        lines.append(
            "Use only outer shape and placement for marked panels. Fill interiors with smooth blank material."
        )
    return "\n".join(lines)


def blank_prompt(refs, blank_surface_guard):
    """V9's auto-prompt over the toward cards, plus a counter-example line."""
    if not refs:
        return ""

    if blank_surface_guard and all(ref["role"] == "text/logo safe" for ref in refs):
        return _v9_prompts.blank_prompt(refs, blank_surface_guard)

    toward = [ref for ref in refs if ref.get("direction", "toward") != "away"]
    away = [ref for ref in refs if ref.get("direction", "toward") == "away"]

    base = _v9_prompts.blank_prompt(toward, blank_surface_guard) if toward else ""
    if not base:
        base = "Create a new clean cohesive image."
        if blank_surface_guard:
            base += " Keep every guarded surface smooth, empty, plain, clean, undecorated, and completely unmarked."
    if away:
        base += " Steer the overall result away from each counter-example source's look."
    return base.strip()


# Starter guard vocabulary for Latin-script languages beyond English.
# Same replacement targets as the V9 tables; words that collide with common
# English words (cartel, parole, etiquette, manifesto, nombres) are left out
# on purpose. Extending this list is a data change (technical paper section
# 16.6). CJK languages need non-regex word handling and are out of scope.
EXTRA_NEGATION_PATTERN = re.compile(
    r"\b(?:sin|sans|ohne|sem|senza)\s+(?:\w+\s)?"
    r"(?:texts?|textos?|textes?|testo|testi|palabras?|palavras?|mots|w[öo]rter|worte|buchstaben|"
    r"letras?|lettres?|lettere|logos?|logotipos?|s[ií]mbolos?|symboles?|simboli)\b",
    re.IGNORECASE,
)

EXTRA_MARKING_REPLACEMENTS = {
    # board / sign
    r"\bletreros?\b": "plain blank board",          # Spanish
    r"\br[óo]tulos?\b": "plain blank board",        # Spanish/Portuguese
    r"\bletreiros?\b": "plain blank board",         # Portuguese
    r"\bpanneaux?\b": "plain blank board",          # French
    r"\benseignes?\b": "plain blank board",         # French
    r"\bschild(?:er)?\b": "plain blank board",      # German
    r"\bplacas?\b": "plain blank board",            # Spanish/Portuguese
    r"\binsegn[ae]\b": "plain blank board",         # Italian
    r"\bcartell[oi]\b": "plain blank board",        # Italian
    # label
    r"\betiquetas?\b": "plain blank surface",       # Spanish/Portuguese
    r"\bétiquettes?\b": "plain blank surface",      # French (accented form only)
    r"\betikett(?:en)?\b": "plain blank surface",   # German
    r"\betichett[ae]\b": "plain blank surface",     # Italian
    # poster
    r"\bafiches?\b": "plain blank panel",           # Spanish
    r"\baffiches?\b": "plain blank panel",          # French
    r"\bplakate?\b": "plain blank panel",           # German
    r"\bcartaz(?:es)?\b": "plain blank panel",      # Portuguese
    # text / writing
    r"\btextos?\b": "plain surface",                # Spanish/Portuguese
    r"\btextes?\b": "plain surface",                # French
    r"\btest[oi]\b": "plain surface",               # Italian
    r"\bescrituras?\b": "plain surface",            # Spanish
    r"\bescritas?\b": "plain surface",              # Portuguese
    r"\bécritures?\b": "plain surface",             # French (accented form only)
    r"\bschrift(?:en)?\b": "plain surface",         # German
    r"\bbeschriftung(?:en)?\b": "plain surface",    # German
    r"\bscritt[ae]\b": "plain surface",             # Italian
    # words / letters
    r"\bpalabras?\b": "plain surface",              # Spanish
    r"\bpalavras?\b": "plain surface",              # Portuguese
    r"\bmots\b": "plain surface",                   # French (plural only; "mot" collides with English)
    r"\bw[öo]rter\b": "plain surface",              # German
    r"\bworte\b": "plain surface",                  # German
    r"\bparola\b": "plain surface",                 # Italian (singular only; "parole" collides with English)
    r"\bletras\b": "plain surface",                 # Spanish/Portuguese
    r"\blettres\b": "plain surface",                # French
    r"\bbuchstaben\b": "plain surface",             # German
    r"\blettere\b": "plain surface",                # Italian
    # logo / symbols / numbers
    r"\blogotipos?\b": "plain blank mark-free area",  # Spanish/Portuguese
    r"\bs[ií]mbolos?\b": "plain surface",           # Spanish/Portuguese
    r"\bsymboles?\b": "plain surface",              # French
    r"\bsimboli\b": "plain surface",                # Italian
    r"\bn[úu]meros?\b": "plain surface",            # Spanish/Portuguese
    r"\bchiffres?\b": "plain surface",              # French
}


def sanitize_text_logo_prompt(prompt_text):
    """Rewrite marking words in five extra languages, then run the V9 pass."""
    text = str(prompt_text or "")
    text = EXTRA_NEGATION_PATTERN.sub("plain unmarked", text)
    for pattern, replacement in EXTRA_MARKING_REPLACEMENTS.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return _v9_prompts.sanitize_text_logo_prompt(text)
