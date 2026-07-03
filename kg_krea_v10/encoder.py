"""The V10 reference-stack encoder node.

Same delta architecture as V9 (encode the prompt with every reference
active, isolate each ingredient's delta by re-encoding with it muted,
re-add the deltas at per-card strengths), with four V10 additions:

- Direction: "away" cards re-add their delta negatively, turning a
  reference into a counter-example.
- Balance: an optional per-phase budget on the summed departure from
  neutral, so several simultaneously hot cards degrade gracefully.
- Study reuse: deltas depend only on content (never on strengths), so a
  content-keyed cache makes strength/timing tweaks compose-only.
- Feedback: a plain-language stack report and a contact sheet of the
  prepared references are returned alongside the conditioning.

The private methods that wrap sibling modules (_encode_with_controls,
_compose_conditioning, ...) are a stable seam the contract tests patch;
keep them defined on this class.
"""

from . import cache as study_cache
from . import preview, prompts, recipes
from . import report as stack_report
from ._v9 import v9

KG_KREA_REFERENCE_TYPE = v9.KG_KREA_REFERENCE_TYPE


class KGTextEncodeKreaImageReferencesV10:
    """
    KG Prefix: Krea 2 Reference Stack Encoder V10

    Reads guide-card packets (V9 or V10) and builds Krea conditioning, a
    plain-language stack report, and a prepared-reference contact sheet.
    """

    MAX_REFERENCE_CARDS = 12

    # Effective per-layer scale is clamped to +/- this value so recipe spikes
    # times a hot card strength cannot push a single layer's delta
    # arbitrarily far past encode-native scale in either direction.
    MAX_LAYER_SCALE = 6.0

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

    BALANCE_LABELS = {
        "off - use my values": "off",
        "gentle balance": "gentle",
        "strict balance": "strict",
    }

    REUSE_LABELS = {
        "reuse between runs - faster tuning": True,
        "always re-study": False,
    }

    @classmethod
    def _reference_card_inputs(cls):
        return {
            f"Reference {i} guide card": (KG_KREA_REFERENCE_TYPE,)
            for i in range(1, cls.MAX_REFERENCE_CARDS + 1)
        }

    @classmethod
    def INPUT_TYPES(cls):
        # Widget labels are the saved-workflow API: the first nine rows
        # repeat the V9 stack's frozen surface, and the V10 rows are appended
        # after. Append new labels only; never rename or reorder.
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
                "Balance strong cards": (list(cls.BALANCE_LABELS.keys()),),
                "Reuse image studies": (list(cls.REUSE_LABELS.keys()),),
            },
            "optional": cls._reference_card_inputs(),
        }

    RETURN_TYPES = ("CONDITIONING", "STRING", "IMAGE")
    RETURN_NAMES = ("conditioning", "stack_report", "prepared_references")
    FUNCTION = "execute"
    CATEGORY = "advanced/conditioning"

    # -- module seams (patched by the contract tests; keep on the class) ----

    @staticmethod
    def _tag_image_references(tokens):
        v9.qwen_tokens.tag_image_references(tokens)

    @staticmethod
    def _encode_with_controls(clip, tokens, image_scales=None, mute_prompt=False, get_prompt_bounds=None):
        return v9.clip_hooks.encode_with_controls(
            clip,
            tokens,
            image_scales=image_scales,
            mute_prompt=mute_prompt,
            get_prompt_bounds=get_prompt_bounds,
        )

    @staticmethod
    def _conditioning_delta(full_conditioning, muted_conditioning):
        return v9.conditioning.conditioning_delta(full_conditioning, muted_conditioning)

    @staticmethod
    def _apply_prompt_delta(full_conditioning, muted_conditioning):
        return v9.conditioning.apply_prompt_delta(full_conditioning, muted_conditioning)

    @staticmethod
    def _compose_conditioning(full_conditioning, weighted_deltas):
        return v9.conditioning.compose_conditioning(full_conditioning, weighted_deltas)

    @staticmethod
    def _with_timestep_range(ranged_conditioning, start, end):
        return v9.conditioning.with_timestep_range(ranged_conditioning, start, end)

    @staticmethod
    def _blur_samples(samples, kernel_size):
        return v9.images.blur_samples(samples, kernel_size)

    @staticmethod
    def _prepare_image_v10(image, reference_resolution, reference_fit, reference_treatment, reference_detail, color_keep):
        return v9.images.prepare_image(image, reference_resolution, reference_fit, reference_treatment, reference_detail, color_keep)

    @staticmethod
    def _effective_image_strength_v10(raw_strength, curve):
        return recipes.effective_image_strength(raw_strength, curve)

    @staticmethod
    def _role_pull_defaults(role):
        return recipes.role_pull_defaults(role)

    @staticmethod
    def _role_layer_pull_defaults(role):
        return recipes.role_layer_pull_defaults(role)

    @staticmethod
    def _cache_key(clip, prompt_text, template_text, prepared_images):
        return study_cache.make_key(clip, prompt_text, template_text, prepared_images)

    @staticmethod
    def _cache_lookup(key, clip):
        return study_cache.lookup(key, clip)

    @staticmethod
    def _cache_store(key, clip, full_conditioning, deltas):
        study_cache.store(key, clip, full_conditioning, deltas)

    @staticmethod
    def _build_report(info):
        return stack_report.build_report(info)

    @staticmethod
    def _build_contact_sheet(prepared_images):
        return preview.contact_sheet(prepared_images)

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
        return cards

    @staticmethod
    def _card_value(card, resolved_key, fallback_key, default):
        if resolved_key in card:
            return card.get(resolved_key)
        return card.get(fallback_key, default)

    # -- execute steps -------------------------------------------------------

    def _read_stack_settings(self, kwargs):
        """Map the stack's own widgets from labels to internal values."""
        balance_mode = self.BALANCE_LABELS.get(kwargs.get("Balance strong cards", "off - use my values"), "off")
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
            "balance_budget": recipes.BALANCE_BUDGETS.get(balance_mode),
            "reuse_studies": bool(
                self.REUSE_LABELS.get(kwargs.get("Reuse image studies", "reuse between runs - faster tuning"), True)
            ),
        }

    def _collect_references(self, kwargs, stack):
        """Resolve connected guide cards into prepared reference entries.

        Returns (refs, skipped, blank_surface_guard); cards without an image
        or with zero effective strength are skipped and cost nothing, and
        the skip reason is surfaced in the stack report.
        """
        refs = []
        skipped = []
        blank_surface_guard = False
        for index, card in self._connected_reference_cards(kwargs):
            if not isinstance(card, dict):
                skipped.append({"index": index, "reason": "not a guide-card packet"})
                continue
            image = card.get("image")
            effective_strength = self._effective_image_strength_v10(card.get("strength", 0.0), stack["strength_curve"])
            if image is None:
                skipped.append({"index": index, "reason": "no image connected"})
                continue
            if effective_strength <= 0.0:
                skipped.append({"index": index, "reason": "strength 0 - costs nothing"})
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
            direction = self._card_value(card, "resolved_direction", "direction", "toward")
            timing = self._card_value(card, "resolved_timing", "timing", "recipe")
            default_shape_pull, default_global_pull = self._role_pull_defaults(role)
            shape_pull = self._card_value(card, "resolved_shape_pull", "shape_pull", default_shape_pull)
            global_pull = self._card_value(card, "resolved_global_pull", "global_pull", default_global_pull)
            layer_pull = self._card_value(card, "resolved_layer_pull", "layer_pull", self._role_layer_pull_defaults(role))
            guarded = bool(card.get("v9_blank_surface_guard")) or role == "text/logo safe"
            blank_surface_guard = blank_surface_guard or guarded

            if reference_resolution in (None, "stack"):
                reference_resolution = stack["resolution"]
            if reference_fit in (None, "stack"):
                reference_fit = stack["fit"]

            refs.append({
                "image": self._prepare_image_v10(image, reference_resolution, reference_fit, treatment, detail, color_keep),
                "strength": effective_strength,
                "role": role,
                "subject_policy": subject_policy,
                "direction": "away" if direction == "away" else "toward",
                "early_multiplier": max(0.0, float(early_multiplier)),
                "late_multiplier": max(0.0, float(late_multiplier)),
                "shape_pull": max(0.0, float(shape_pull)),
                "global_pull": max(0.0, float(global_pull)),
                "layer_pull": [max(0.0, float(value)) for value in list(layer_pull)],
                # Report bookkeeping (never read by the conditioning math).
                "card_index": index,
                "purpose": card.get("purpose", "hand-built packet"),
                "requested_strength": float(card.get("requested_strength", card.get("strength", 0.0))),
                "packet_strength": float(card.get("strength", 0.0)),
                "strength_cap": card.get("v9_strength_cap"),
                "guarded": guarded,
                "timing": timing,
            })
        return refs, skipped, blank_surface_guard

    @staticmethod
    def _resolve_prompt(prompt, prompt_strength, refs, blank_surface_guard, guard_prompt_mode):
        """Choose the encoded prompt text, its strength, and report notes.

        Same policy as V9 (empty prompt falls back to role-derived language;
        the full guard rewrites marking words and floors the strength; the
        gentle guard only appends the blank-surface suffix), with the V10
        multilingual sanitizer and every decision noted for the report.
        """
        prompt_text = str(prompt or "").strip()
        notes = []
        auto_prompt = not prompt_text
        prompt_for_encoding = prompt_text or prompts.blank_prompt(refs, blank_surface_guard)
        if auto_prompt and prompt_for_encoding:
            notes.append("no prompt written - role-derived prompt used")
        if blank_surface_guard:
            if prompt_text and guard_prompt_mode == "full":
                prompt_for_encoding = prompts.sanitize_text_logo_prompt(prompt_text)
                notes.append("full guard rewrote marking words in the prompt")
            guard_suffix = prompts.text_logo_guard_suffix()
            prompt_for_encoding = (prompt_for_encoding + "\n\n" + guard_suffix).strip() if prompt_for_encoding else guard_suffix
        effective_prompt_strength = float(prompt_strength)
        if auto_prompt and prompt_for_encoding and effective_prompt_strength <= 0.0:
            effective_prompt_strength = 1.0
        if blank_surface_guard and guard_prompt_mode == "full":
            floored = max(effective_prompt_strength, 3.5)
            if floored > effective_prompt_strength:
                notes.append("prompt strength floored to 3.50 by the full guard")
            effective_prompt_strength = floored
        return prompt_for_encoding, effective_prompt_strength, notes

    @classmethod
    def _reference_targets(cls, refs, multiplier_name=None):
        """Per-image token/pooled/layer targets for one sampling phase.

        Away cards negate their targets, so their delta is re-added in the
        opposite direction (t < 0 pushes past removal into repulsion).
        """
        max_layer_scale = float(cls.MAX_LAYER_SCALE)
        targets = []
        for ref in refs:
            phase_multiplier = float(ref[multiplier_name]) if multiplier_name else 1.0
            sign = -1.0 if ref.get("direction") == "away" else 1.0
            base_strength = ref["strength"] * phase_multiplier
            token_target = sign * base_strength * ref["shape_pull"]
            targets.append({
                "token": token_target,
                "token_layers": [
                    min(max(token_target * layer_gain, -max_layer_scale), max_layer_scale) - 1.0
                    for layer_gain in ref["layer_pull"]
                ],
                "pooled": sign * base_strength * ref["global_pull"],
            })
        return targets

    @staticmethod
    def _balance_targets(targets, budget):
        """Scale one phase's departures from neutral down to the budget.

        Returns the applied scale (1.0 when nothing was scaled). Multi-card
        first-order composition degrades with the total departure from
        neutral, so the budget softly renormalizes hot stacks instead of
        letting them fight.
        """
        if budget is None or not targets:
            return 1.0
        departure = sum(
            max(abs(target["token"] - 1.0), abs(target["pooled"] - 1.0))
            for target in targets
        )
        if departure <= float(budget) or departure <= 0.0:
            return 1.0
        scale = float(budget) / departure
        for target in targets:
            target["token"] = 1.0 + (target["token"] - 1.0) * scale
            target["pooled"] = 1.0 + (target["pooled"] - 1.0) * scale
            target["token_layers"] = [weight * scale for weight in target["token_layers"]]
        return scale

    @staticmethod
    def _image_delta_needed(target_sets, image_index):
        """True when any phase moves this image off neutral (1.0 / no layers)."""
        return any(
            abs(targets[image_index]["token"] - 1.0) > 0.00001
            or abs(targets[image_index]["pooled"] - 1.0) > 0.00001
            or any(abs(value) > 0.00001 for value in targets[image_index].get("token_layers", []))
            for targets in target_sets
        )

    def _encode_missing_deltas(self, clip, tokens, full_conditioning, reference_count, effective_prompt_strength, target_sets, delta_cache):
        """Encode only the ingredient deltas the cache does not already hold.

        Keys: "prompt" for the written-prompt delta (only when its strength
        is not 1.0), and the image index for each non-neutral reference.
        Returns (new encoder passes, reused cached deltas) for the report.
        """
        new_encodes = 0
        reused = 0

        if effective_prompt_strength != 1.0:
            if "prompt" in delta_cache:
                reused += 1
            else:
                def get_prompt_bounds(token_rows, embeds_info):
                    image_embedding_sizes = v9.qwen_tokens.image_embedding_sizes(embeds_info)
                    return v9.qwen_tokens.prompt_input_embedding_bounds(token_rows, image_embedding_sizes, reference_count)

                muted_conditioning = self._encode_with_controls(clip, tokens, mute_prompt=True, get_prompt_bounds=get_prompt_bounds)
                delta_cache["prompt"] = self._apply_prompt_delta(full_conditioning, muted_conditioning)
                new_encodes += 1

        for image_index in range(reference_count):
            if self._image_delta_needed(target_sets, image_index):
                if image_index in delta_cache:
                    reused += 1
                else:
                    muted_image_conditioning = self._encode_with_controls(clip, tokens, image_scales={image_index: 0.0})
                    delta_cache[image_index] = self._conditioning_delta(full_conditioning, muted_image_conditioning)
                    new_encodes += 1

        return new_encodes, reused

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
        refs, skipped, blank_surface_guard = self._collect_references(kwargs, stack)

        prompt_for_encoding, effective_prompt_strength, prompt_notes = self._resolve_prompt(
            kwargs.get("Final image prompt", ""),
            kwargs.get("Written prompt strength", 1.0),
            refs,
            blank_surface_guard,
            stack["guard_prompt_mode"],
        )

        system_prompt = prompts.role_system_prompt(refs, blank_surface_guard)
        full_prompt = prompts.image_pad_prefix(len(refs)) + prompt_for_encoding
        llama_template = prompts.llama_template(system_prompt)
        prepared_images = [ref["image"] for ref in refs]
        tokens = clip.tokenize(full_prompt, images=prepared_images, llama_template=llama_template)
        self._tag_image_references(tokens)

        cache_key = None
        cached = None
        if stack["reuse_studies"]:
            cache_key = self._cache_key(clip, full_prompt, llama_template, prepared_images)
            cached = self._cache_lookup(cache_key, clip)
        if cached is None:
            full_conditioning = self._encode_with_controls(clip, tokens)
            delta_cache = {}
            base_encodes, base_reused = 1, 0
        else:
            full_conditioning = cached["full"]
            delta_cache = dict(cached["deltas"])
            base_encodes, base_reused = 0, 1

        two_phase = stack["schedule"] in ("smart", "two phase")
        if two_phase:
            target_sets = [
                self._reference_targets(refs, "early_multiplier"),
                self._reference_targets(refs, "late_multiplier"),
            ]
        else:
            target_sets = [self._reference_targets(refs)]

        balance_scales = [self._balance_targets(targets, stack["balance_budget"]) for targets in target_sets]

        new_encodes, reused_deltas = self._encode_missing_deltas(
            clip, tokens, full_conditioning, len(refs), effective_prompt_strength, target_sets, delta_cache
        )
        if cache_key is not None:
            self._cache_store(cache_key, clip, full_conditioning, delta_cache)

        if two_phase:
            split = min(max(float(stack["schedule_split"]), 0.0), 1.0)
            early_conditioning = self._compose_for_targets(full_conditioning, delta_cache, effective_prompt_strength, target_sets[0])
            late_conditioning = self._compose_for_targets(full_conditioning, delta_cache, effective_prompt_strength, target_sets[1])
            if split <= 0.0:
                conditioning_out = self._with_timestep_range(late_conditioning, 0.0, 1.0)
            elif split >= 1.0:
                conditioning_out = self._with_timestep_range(early_conditioning, 0.0, 1.0)
            else:
                conditioning_out = self._with_timestep_range(early_conditioning, 0.0, split)
                conditioning_out += self._with_timestep_range(late_conditioning, split, 1.0)
        else:
            conditioning_out = self._compose_for_targets(full_conditioning, delta_cache, effective_prompt_strength, target_sets[0])

        cards_info = [
            {
                "index": ref["card_index"],
                "purpose": ref["purpose"],
                "direction": ref["direction"],
                "requested": ref["requested_strength"],
                "packet_strength": ref["packet_strength"],
                "effective": ref["strength"],
                "cap": ref["strength_cap"],
                "guard": ref["guarded"],
                "timing": ref["timing"],
                "targets": [(targets[i]["token"], targets[i]["pooled"]) for targets in target_sets],
            }
            for i, ref in enumerate(refs)
        ]
        report_text = self._build_report({
            "prompt_text": prompt_for_encoding,
            "prompt_strength": effective_prompt_strength,
            "prompt_notes": prompt_notes,
            "timing_label": kwargs.get("When images guide", "smart per-card timing"),
            "two_phase": two_phase,
            "split": stack["schedule_split"],
            "balance_label": kwargs.get("Balance strong cards", "off - use my values"),
            "balance_budget": stack["balance_budget"],
            "balance_scales": balance_scales,
            "reuse": stack["reuse_studies"],
            "encodes_done": base_encodes + new_encodes,
            "reused_studies": base_reused + reused_deltas,
            "cards": cards_info,
            "skipped": skipped,
            "blank_surface_guard": blank_surface_guard,
            "layer_fallback": bool(getattr(v9.conditioning, "_layer_fallback_warned", False)),
        })
        contact_sheet = self._build_contact_sheet(prepared_images)

        return (conditioning_out, report_text, contact_sheet)
