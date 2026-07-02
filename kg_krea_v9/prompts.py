"""Prompt text construction for the V9 stack encoder.

Builds the system prompt that assigns each reference its role, the fallback
prompt used when the artist writes nothing, and the text/logo guard language.
The full guard rewrites marking words in the written prompt; the gentle
guard leaves the artist's words alone and only appends the blank-surface
suffix (see the encoder's "Text/logo guard prompt handling" widget).
"""

import re

ROLE_INSTRUCTIONS = {
    "balanced": "use as general visual guidance",
    "style": "borrow palette, tonal feel, medium, art direction, rendering finish, and atmosphere without copying the style reference subject",
    "palette": "borrow broad color palette, contrast, and tonal relationship only; avoid subject, layout, and texture copying",
    "composition": "borrow pose, subject placement, spacing, camera angle, crop, and scene structure more than identity or surface style",
    "framing": "borrow camera distance, crop, lens feel, viewpoint, and framing only",
    "identity": "preserve the main source subject, recognizable visual cues, product shape, object design, and proportions when relevant",
    "environment": "borrow background, location type, scene context, spatial atmosphere, and environmental cues without replacing the main subject",
    "lighting": "borrow lighting direction, contrast, mood, color cast, glow, and shadow behavior",
    "material": "borrow material feel, surface quality, finish, and tactile impression without copying exact grain, text, or tiny marks",
    "loose": "treat as loose mood-board inspiration only; avoid copying specific details unless the user asks",
    "shape only": "borrow broad silhouette, spacing, and geometric structure only; ignore color, texture, text, logos, and small details",
    "text/logo safe": "borrow only broad blank shape and layout; treat writing, logos, symbols, UI, and letter-like detail as empty surfaces that should not be reproduced",
}

SUBJECT_POLICY_INSTRUCTIONS = {
    "avoid": "Do not copy this reference image's subject identity, face, product identity, outfit, or object design.",
    "allow": "This reference may influence subject details only when that helps the user's requested result.",
    "preserve": "Preserve this reference image's main subject or product identity as an important content source.",
    "recipe": "Use only the subject behavior implied by this reference role.",
}


def blank_surface_positive():
    """The positive phrasing used everywhere the guard wants empty surfaces."""
    return "smooth empty blank panel, plain clean featureless surface, undecorated unmarked interior, simple stand"


def text_logo_guard_suffix():
    return blank_surface_positive()


def role_system_prompt(refs, blank_surface_guard):
    """Build the system prompt assigning each reference input its role."""
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
        subject_policy = ref.get("subject_policy", "recipe")
        if blank_surface_guard and role == "text/logo safe":
            lines.append("Input {}: blank panel shape only, smooth empty interior.".format(i))
        else:
            lines.append("Input {} role: {}.".format(i, ROLE_INSTRUCTIONS.get(role, ROLE_INSTRUCTIONS["balanced"])))
        policy_text = SUBJECT_POLICY_INSTRUCTIONS.get(subject_policy)
        if policy_text and subject_policy != "recipe" and not (blank_surface_guard and role == "text/logo safe"):
            lines.append("Input {} subject rule: {}.".format(i, policy_text))
    if blank_surface_guard:
        lines.append(
            "Use only outer shape and placement for marked panels. Fill interiors with smooth blank material."
        )
    return "\n".join(lines)


def blank_prompt(refs, blank_surface_guard):
    """Build the written prompt used when the artist leaves the prompt empty."""
    if not refs:
        return ""

    if blank_surface_guard and all(ref["role"] == "text/logo safe" for ref in refs):
        return blank_surface_positive()

    lines = [
        "Create a cohesive final image from the connected visual sources.",
    ]
    if any(ref["role"] in {"identity", "balanced"} or ref.get("subject_policy") == "preserve" for ref in refs):
        lines.append("Keep the main subject, recognizable content, object shape, proportions, pose, camera, and layout from the primary content source.")
    if any(ref["role"] in {"composition", "framing"} for ref in refs):
        lines.append("Use pose, camera distance, crop, spacing, viewpoint, and layout from the structure source.")
    if any(ref["role"] == "environment" for ref in refs):
        lines.append("Use background, location, scene context, and spatial atmosphere from the environment source.")
    if any(ref["role"] == "lighting" for ref in refs):
        lines.append("Use light direction, shadow behavior, contrast, color cast, glow, and mood from the lighting source.")
    if any(ref["role"] == "style" for ref in refs):
        lines.append("Apply palette, tonal feel, medium, rendering finish, and atmosphere from the style source while keeping the style source subject out.")
    if any(ref["role"] == "palette" for ref in refs):
        lines.append("Apply color palette and tonal relationships from the palette source only.")
    if any(ref["role"] == "material" for ref in refs):
        lines.append("Apply material feel and surface finish from the material source without exact grain or tiny marks.")
    if any(ref["role"] == "loose" for ref in refs):
        lines.append("Use loose mood-board inspiration without copying specific details.")
    if any(ref["role"] == "shape only" for ref in refs):
        lines.append("Use broad silhouette, spacing, and geometric structure only.")
    if any(ref["role"] == "text/logo safe" for ref in refs):
        lines.append("Use any marked panel as a smooth blank shape with an empty interior surface.")
    if any(ref.get("subject_policy") == "avoid" for ref in refs):
        lines.append("Keep avoided-source subject identity out of the final image.")

    if blank_surface_guard:
        lines.append("Keep every guarded surface smooth, empty, plain, clean, undecorated, and completely unmarked.")

    return " ".join(lines)


def sanitize_text_logo_prompt(prompt_text):
    """Rewrite marking words so the prompt stops asking for text or logos.

    Negated requests ("no text") and marking nouns ("sign", "logo", "label")
    both become blank-surface language, since the encoder renders the words
    it reads either way.
    """
    text = str(prompt_text or "")
    negative_marking_pattern = re.compile(
        r"\b(?:no|without|free of)\s+(?:readable\s+)?(?:text|writing|words?|letters?|numbers?|logos?|symbols?|glyphs?|brand(?:ed)?\s+marks?|marks?|markings?)\b",
        re.IGNORECASE,
    )
    text = negative_marking_pattern.sub("plain unmarked", text)
    replacements = {
        r"\bsignage\b": "plain blank board",
        r"\bsigns?\b": "plain blank board",
        r"\blabels?\b": "plain blank surface",
        r"\bscreens?\b": "plain blank surface",
        r"\bposters?\b": "plain blank panel",
        r"\bpatches\b": "plain blank patch",
        r"\btags?\b": "plain blank tag",
        r"\blogos?\b": "plain blank mark-free area",
        r"\bUI\b": "plain blank interface surface",
        r"\btext\b": "plain surface",
        r"\bwriting\b": "plain surface",
        r"\bwords?\b": "plain surface",
        r"\bletters?\b": "plain surface",
        r"\bnumbers?\b": "plain surface",
        r"\bsymbols?\b": "plain surface",
        r"\bglyphs?\b": "plain surface",
    }
    for pattern, replacement in replacements.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip()
    prefix = "Create the requested scene with smooth blank unmarked surfaces wherever the reference has markings."
    return (prefix + " " + text).strip()


def llama_template(system_prompt):
    """Chat template with the system prompt baked in and the user slot open."""
    return "<|im_start|>system\n{}<|im_end|>\n<|im_start|>user\n{{}}<|im_end|>\n<|im_start|>assistant\n".format(system_prompt)


def image_pad_prefix(reference_count):
    """One vision placeholder line per connected reference image."""
    return "<|vision_start|><|image_pad|><|vision_end|>\n" * reference_count
