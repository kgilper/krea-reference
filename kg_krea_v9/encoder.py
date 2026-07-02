"""The V9 reference-stack encoder node.

Reads guide-card packets and builds Krea conditioning directly: encode the
prompt with every reference active, isolate each ingredient's delta by
re-encoding with it muted, then re-add the deltas at per-card strengths
(optionally split into early/late sampling phases).

Performance note: each connected card whose targets differ from neutral
costs one extra text-encoder pass (the encode-with-this-image-muted delta),
plus one more pass when the written prompt strength is not 1.0. Encode time
grows roughly linearly with the number of active cards.

The heavy lifting lives in sibling modules (clip_hooks, conditioning,
images, prompts, qwen_tokens, recipes). The private methods that wrap them
(_encode_with_controls, _compose_conditioning, ...) are a stable seam the
contract tests patch; keep them defined on this class.
"""

from . import clip_hooks, conditioning, images, prompts, qwen_tokens, recipes
from .constants import KG_KREA_REFERENCE_TYPE


class KGTextEncodeKreaImageReferencesV9:
    """
    KG Prefix: Krea 2 Reference Stack Encoder V9

    Reads guide-card packets and builds Krea conditioning directly. The stack
    exposes guarded prompt handling, soft-capped per-layer gains, and a
    once-per-process warning when the layered conditioning path is unavailable.
    """

    MAX_REFERENCE_CARDS = 12

    # Effective per-layer scale is clamped to this value so recipe spikes
    # (up to 5.5x) times a hot card strength cannot push a single layer's
    # delta arbitrarily far past encode-native scale.
    MAX_LAYER_SCALE = 6.0

    # Prompt-text tables live in prompts.py; the class aliases preserve the
    # original single-module surface for external callers.
    ROLE_INSTRUCTIONS = prompts.ROLE_INSTRUCTIONS
    SUBJECT_POLICY_INSTRUCTIONS = prompts.SUBJECT_POLICY_INSTRUCTIONS

    STRENGTH_BEHAVIOR_LABELS = {
        "artist friendly - soft at low values": "artist",
        "literal slider values": "linear",
        "extra gentle for stubborn references": "extra gentle",
    }

    DETAIL_LEVEL_LABELS = {
        "low - loose idea (256)": "256",
        "medium - balanced default (384)": "384",
        "high - more exact (512)": "512",
        "very high - most exact (768)": "768",
    }

    FRAMING_LABELS = {
        "keep full image shape": "preserve aspect",
        "center crop square": "center crop square",
        "stretch to square": "stretch square",
    }

    TIMING_LABELS = {
        "smart per-card timing": "smart",
        "guide the whole image": "constant",
        "layout early, details later": "two phase",
    }

    GUARD_PROMPT_LABELS = {
        "full guard - rewrite my prompt": "full",
        "gentle guard - keep my prompt words": "gentle",
    }

    @classmethod
    def _reference_card_inputs(cls):
        return {
            f"Reference {i} guide card": (KG_KREA_REFERENCE_TYPE,)
            for i in range(1, cls.MAX_REFERENCE_CARDS + 1)
        }

    @classmethod
    def INPUT_TYPES(cls):
        # Widget labels are the saved-workflow API: renaming any label breaks
        # existing workflows and API-format calls. Treat them as frozen.
        return {
            "required": {
                "Krea CLIP": ("CLIP",),
                "Final image prompt": ("STRING", {"multiline": True, "dynamic_prompts": True}),
                "Written prompt strength": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 10.0, "step": 0.05}),
                "Image slider feel": (list(cls.STRENGTH_BEHAVIOR_LABELS.keys()),),
                "Image detail level": (list(cls.DETAIL_LEVEL_LABELS.keys()),),
                "Image framing": (list(cls.FRAMING_LABELS.keys()),),
                "When images guide": (list(cls.TIMING_LABELS.keys()),),
                "Early-to-final handoff": ("FLOAT", {"default": 0.40, "min": 0.0, "max": 1.0, "step": 0.01}),
                "Text/logo guard prompt handling": (list(cls.GUARD_PROMPT_LABELS.keys()),),
            },
            "optional": cls._reference_card_inputs(),
        }

    RETURN_TYPES = ("CONDITIONING",)
    FUNCTION = "execute"
    CATEGORY = "advanced/conditioning"

    # -- module seams (patched by the contract tests; keep on the class) ----

    @staticmethod
    def _tag_image_references(tokens):
        qwen_tokens.tag_image_references(tokens)

    @staticmethod
    def _encode_with_controls(clip, tokens, image_scales=None, mute_prompt=False, get_prompt_bounds=None):
        return clip_hooks.encode_with_controls(
            clip,
            tokens,
            image_scales=image_scales,
            mute_prompt=mute_prompt,
            get_prompt_bounds=get_prompt_bounds,
        )

    @staticmethod
    def _conditioning_delta(full_conditioning, muted_conditioning):
        return conditioning.conditioning_delta(full_conditioning, muted_conditioning)

    @staticmethod
    def _apply_prompt_delta(full_conditioning, muted_conditioning):
        return conditioning.apply_prompt_delta(full_conditioning, muted_conditioning)

    @staticmethod
    def _compose_conditioning(full_conditioning, weighted_deltas):
        return conditioning.compose_conditioning(full_conditioning, weighted_deltas)

    @staticmethod
    def _with_timestep_range(ranged_conditioning, start, end):
        return conditioning.with_timestep_range(ranged_conditioning, start, end)

    @staticmethod
    def _blur_samples(samples, kernel_size):
        return images.blur_samples(samples, kernel_size)

    @staticmethod
    def _prepare_image_v9(image, reference_resolution, reference_fit, reference_treatment, reference_detail, color_keep):
        return images.prepare_image(image, reference_resolution, reference_fit, reference_treatment, reference_detail, color_keep)

    @staticmethod
    def _effective_image_strength_v9(raw_strength, curve):
        return recipes.effective_image_strength(raw_strength, curve)

    @staticmethod
    def _role_pull_defaults(role):
        return recipes.role_pull_defaults(role)

    @staticmethod
    def _role_layer_pull_defaults(role):
        return recipes.role_layer_pull_defaults(role)

    # -- guide-card packet reading ------------------------------------------

    @staticmethod
    def _map_label(mapping, value):
        return mapping.get(value, value)

    @staticmethod
    def _reference_card_index(name):
        parts = str(name).split()
        if len(parts) == 4 and parts[0] == "Reference" and parts[2] == "guide" and parts[3] == "card" and parts[1].isdigit():
            return int(parts[1])
        return None

    def _connected_reference_cards(self, kwargs):
        cards = []
        for key, value in kwargs.items():
            index = self._reference_card_index(key)
            if index is None or value is None:
                continue
            cards.append((index, value))
        cards.sort(key=lambda item: item[0])
        return [card for _, card in cards]

    @staticmethod
    def _card_value(card, resolved_key, fallback_key, default):
        if resolved_key in card:
            return card.get(resolved_key)
        return card.get(fallback_key, default)

    # -- execute steps -------------------------------------------------------

    def _read_stack_settings(self, kwargs):
        """Map the stack's own widgets from labels to internal values."""
        return {
            "strength_curve": self._map_label(
                self.STRENGTH_BEHAVIOR_LABELS,
                kwargs.get("Image slider feel", "artist friendly - soft at low values"),
            ),
            "resolution": self._map_label(
                self.DETAIL_LEVEL_LABELS,
                kwargs.get("Image detail level", "medium - balanced default (384)"),
            ),
            "fit": self._map_label(
                self.FRAMING_LABELS,
                kwargs.get("Image framing", "keep full image shape"),
            ),
            "schedule": self._map_label(
                self.TIMING_LABELS,
                kwargs.get("When images guide", "smart per-card timing"),
            ),
            "schedule_split": kwargs.get("Early-to-final handoff", 0.40),
            "guard_prompt_mode": self._map_label(
                self.GUARD_PROMPT_LABELS,
                kwargs.get("Text/logo guard prompt handling", "full guard - rewrite my prompt"),
            ),
        }

    def _collect_references(self, kwargs, stack):
        """Resolve connected guide cards into prepared reference entries.

        Returns (refs, blank_surface_guard); cards without an image or with
        zero effective strength are skipped and cost nothing.
        """
        refs = []
        blank_surface_guard = False
        for card in self._connected_reference_cards(kwargs):
            if not isinstance(card, dict):
                continue
            image = card.get("image")
            effective_strength = self._effective_image_strength_v9(card.get("strength", 0.0), stack["strength_curve"])
            if image is None or effective_strength <= 0.0:
                continue

            role = self._card_value(card, "resolved_role", "role", "balanced")
            treatment = self._card_value(card, "resolved_treatment", "treatment", "normal")
            color_keep = self._card_value(card, "resolved_color_keep", "color_keep", 1.0)
            detail = self._card_value(card, "resolved_detail", "detail", 1.0)
            reference_resolution = self._card_value(card, "resolved_reference_resolution", "reference_resolution", "stack")
            reference_fit = self._card_value(card, "resolved_reference_fit", "reference_fit", "stack")
            subject_policy = self._card_value(card, "resolved_subject_policy", "subject_policy", "recipe")
            early_multiplier = self._card_value(card, "resolved_early_multiplier", "early_multiplier", 1.0)
            late_multiplier = self._card_value(card, "resolved_late_multiplier", "late_multiplier", 1.0)
            default_shape_pull, default_global_pull = self._role_pull_defaults(role)
            shape_pull = self._card_value(card, "resolved_shape_pull", "shape_pull", default_shape_pull)
            global_pull = self._card_value(card, "resolved_global_pull", "global_pull", default_global_pull)
            layer_pull = self._card_value(card, "resolved_layer_pull", "layer_pull", self._role_layer_pull_defaults(role))
            blank_surface_guard = (
                blank_surface_guard
                or bool(card.get("v9_blank_surface_guard"))
                or role == "text/logo safe"
            )

            if reference_resolution in (None, "stack"):
                reference_resolution = stack["resolution"]
            if reference_fit in (None, "stack"):
                reference_fit = stack["fit"]

            refs.append({
                "image": self._prepare_image_v9(image, reference_resolution, reference_fit, treatment, detail, color_keep),
                "strength": effective_strength,
                "role": role,
                "subject_policy": subject_policy,
                "early_multiplier": max(0.0, float(early_multiplier)),
                "late_multiplier": max(0.0, float(late_multiplier)),
                "shape_pull": max(0.0, float(shape_pull)),
                "global_pull": max(0.0, float(global_pull)),
                "layer_pull": [max(0.0, float(value)) for value in list(layer_pull)],
            })
        return refs, blank_surface_guard

    @staticmethod
    def _resolve_prompt(prompt, prompt_strength, refs, blank_surface_guard, guard_prompt_mode):
        """Choose the encoded prompt text and the effective prompt strength.

        An empty prompt falls back to role-derived language (at strength 1.0
        if the slider is idle). The full guard rewrites marking words and
        floors the prompt strength; the gentle guard keeps the artist's words
        and strength and only appends the blank-surface suffix.
        """
        prompt_text = str(prompt or "").strip()
        auto_prompt = not prompt_text
        prompt_for_encoding = prompt_text or prompts.blank_prompt(refs, blank_surface_guard)
        if blank_surface_guard:
            if prompt_text and guard_prompt_mode == "full":
                prompt_for_encoding = prompts.sanitize_text_logo_prompt(prompt_text)
            guard_suffix = prompts.text_logo_guard_suffix()
            prompt_for_encoding = (prompt_for_encoding + "\n\n" + guard_suffix).strip() if prompt_for_encoding else guard_suffix
        effective_prompt_strength = float(prompt_strength)
        if auto_prompt and prompt_for_encoding and effective_prompt_strength <= 0.0:
            effective_prompt_strength = 1.0
        if blank_surface_guard and guard_prompt_mode == "full":
            effective_prompt_strength = max(effective_prompt_strength, 3.5)
        return prompt_for_encoding, effective_prompt_strength

    @classmethod
    def _reference_targets(cls, refs, multiplier_name=None):
        """Per-image token/pooled/layer targets for one sampling phase."""
        max_layer_scale = float(cls.MAX_LAYER_SCALE)
        targets = []
        for ref in refs:
            phase_multiplier = float(ref[multiplier_name]) if multiplier_name else 1.0
            base_strength = ref["strength"] * phase_multiplier
            token_target = base_strength * ref["shape_pull"]
            targets.append({
                "token": token_target,
                "token_layers": [
                    min(token_target * layer_gain, max_layer_scale) - 1.0
                    for layer_gain in ref["layer_pull"]
                ],
                "pooled": base_strength * ref["global_pull"],
            })
        return targets

    @staticmethod
    def _image_delta_needed(target_sets, image_index):
        """True when any phase moves this image off neutral (1.0 / no layers)."""
        return any(
            abs(targets[image_index]["token"] - 1.0) > 0.00001
            or abs(targets[image_index]["pooled"] - 1.0) > 0.00001
            or any(abs(value) > 0.00001 for value in targets[image_index].get("token_layers", []))
            for targets in target_sets
        )

    def _encode_deltas(self, clip, tokens, full_conditioning, reference_count, effective_prompt_strength, target_sets):
        """Encode the muted variants and cache each ingredient's delta.

        Keys: "prompt" for the written-prompt delta (only when its strength
        is not 1.0), and the image index for each non-neutral reference.
        """
        delta_cache = {}

        if effective_prompt_strength != 1.0:
            def get_prompt_bounds(token_rows, embeds_info):
                image_embedding_sizes = qwen_tokens.image_embedding_sizes(embeds_info)
                return qwen_tokens.prompt_input_embedding_bounds(token_rows, image_embedding_sizes, reference_count)

            muted_conditioning = self._encode_with_controls(clip, tokens, mute_prompt=True, get_prompt_bounds=get_prompt_bounds)
            delta_cache["prompt"] = self._apply_prompt_delta(full_conditioning, muted_conditioning)

        for image_index in range(reference_count):
            if self._image_delta_needed(target_sets, image_index):
                muted_image_conditioning = self._encode_with_controls(clip, tokens, image_scales={image_index: 0.0})
                delta_cache[image_index] = self._conditioning_delta(full_conditioning, muted_image_conditioning)

        return delta_cache

    def _compose_for_targets(self, full_conditioning, delta_cache, effective_prompt_strength, image_targets):
        """Re-add the cached deltas at one phase's weights."""
        weighted_deltas = []
        if "prompt" in delta_cache:
            weighted_deltas.append((delta_cache["prompt"], effective_prompt_strength - 1.0))
        for image_index, target in enumerate(image_targets):
            if image_index in delta_cache:
                weighted_deltas.append((
                    delta_cache[image_index],
                    float(target["token"]) - 1.0,
                    float(target["pooled"]) - 1.0,
                    target.get("token_layers"),
                ))
        return self._compose_conditioning(full_conditioning, weighted_deltas)

    # -- node entry point ----------------------------------------------------

    def execute(self, **kwargs):
        clip = kwargs.get("Krea CLIP")
        stack = self._read_stack_settings(kwargs)
        refs, blank_surface_guard = self._collect_references(kwargs, stack)

        prompt_for_encoding, effective_prompt_strength = self._resolve_prompt(
            kwargs.get("Final image prompt", ""),
            kwargs.get("Written prompt strength", 1.0),
            refs,
            blank_surface_guard,
            stack["guard_prompt_mode"],
        )

        system_prompt = prompts.role_system_prompt(refs, blank_surface_guard)
        full_prompt = prompts.image_pad_prefix(len(refs)) + prompt_for_encoding
        tokens = clip.tokenize(
            full_prompt,
            images=[ref["image"] for ref in refs],
            llama_template=prompts.llama_template(system_prompt),
        )
        self._tag_image_references(tokens)

        conditioning_out = self._encode_with_controls(clip, tokens)

        two_phase = stack["schedule"] in ("smart", "two phase")
        if two_phase:
            target_sets = [
                self._reference_targets(refs, "early_multiplier"),
                self._reference_targets(refs, "late_multiplier"),
            ]
        else:
            target_sets = [self._reference_targets(refs)]

        delta_cache = self._encode_deltas(
            clip, tokens, conditioning_out, len(refs), effective_prompt_strength, target_sets
        )

        if two_phase:
            split = min(max(float(stack["schedule_split"]), 0.0), 1.0)
            early_conditioning = self._compose_for_targets(conditioning_out, delta_cache, effective_prompt_strength, target_sets[0])
            late_conditioning = self._compose_for_targets(conditioning_out, delta_cache, effective_prompt_strength, target_sets[1])
            if split <= 0.0:
                conditioning_out = self._with_timestep_range(late_conditioning, 0.0, 1.0)
            elif split >= 1.0:
                conditioning_out = self._with_timestep_range(early_conditioning, 0.0, 1.0)
            else:
                conditioning_out = self._with_timestep_range(early_conditioning, 0.0, split)
                conditioning_out += self._with_timestep_range(late_conditioning, split, 1.0)
        else:
            conditioning_out = self._compose_for_targets(conditioning_out, delta_cache, effective_prompt_strength, target_sets[0])

        return (conditioning_out,)
