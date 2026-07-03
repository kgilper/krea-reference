"""User-defined quick recipes for the V10 guide card.

Artists drop `.yaml` / `.yml` / `.json` files into the pack's
`custom_recipes/` folder (or `<ComfyUI user dir>/krea_reference/recipes/`).
Every file that passes schema validation becomes a first-class choice in the
card's "Use image for" dropdown, indistinguishable from a built-in recipe.

Design rules:

- The node always loads. Invalid files are skipped with a logged warning and
  the errors are reported by :func:`refresh`; they never raise into ComfyUI's
  node registration.
- Validation is strict about *keys* (an unknown key is an error, so typos
  cannot silently become no-ops) and forgiving about *omissions* (every
  field except ``label`` and ``role`` has a sensible default derived from
  the role's V9 tuning tables).
- Labels are the identity. A label may not collide with a built-in choice,
  and across files the first definition wins (files scan in sorted order).
  Saved workflows reference custom recipes by label, so renaming or removing
  a recipe file orphans the workflows that use it (the card falls back to
  ``balanced`` with a warning rather than misbehaving).
"""

import json
import logging
from pathlib import Path

from . import recipes as recipe_tables

try:
    import yaml
except ImportError:  # ComfyUI ships PyYAML; degrade to JSON-only without it.
    yaml = None

_logger = logging.getLogger(__name__)

RECIPE_EXTENSIONS = (".yaml", ".yml", ".json")
LAYER_COUNT = 12

ROLES = frozenset(recipe_tables.ROLE_PULL_DEFAULTS)
TREATMENTS = frozenset((
    "normal", "grayscale", "soft blur", "strong blur",
    "palette wash", "color wash", "grayscale blur", "shape wash",
))
STUDY_CHOICES = frozenset(("stack", "256", "384", "512", "768"))
FRAMING_CHOICES = frozenset(("stack", "preserve aspect", "center crop square", "stretch square"))
SUBJECT_CHOICES = frozenset(("recipe", "avoid", "allow", "preserve"))

# field -> (minimum, maximum), matching the card's own clamp ranges.
NUMERIC_RANGES = {
    "color": (0.0, 1.0),
    "detail": (0.0, 1.0),
    "early": (0.0, 5.0),
    "late": (0.0, 5.0),
    "cap": (0.0, 3.0),
    "shape": (0.0, 3.0),
    "global": (0.0, 4.0),
}
LAYER_RANGE = (0.0, 8.0)

REQUIRED_KEYS = frozenset(("label", "role"))
ALLOWED_KEYS = frozenset((
    "label", "description", "role", "treatment", "color", "detail", "study",
    "framing", "subject", "early", "late", "guard", "cap", "shape", "global",
    "layers",
))

# The pack-local drop folder ships with the package (README + template).
_PACK_RECIPE_DIR = Path(__file__).resolve().parents[1] / "custom_recipes"

# Additional Path-like entries appended by tests or power users.
EXTRA_SEARCH_PATHS = []


class RecipeError(ValueError):
    """One recipe (or file) failed validation."""


def _require_number(value, name, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RecipeError("{} must be a number, got {!r}".format(name, value))
    number = float(value)
    if not (minimum <= number <= maximum):
        raise RecipeError("{} must be between {} and {}, got {}".format(name, minimum, maximum, number))
    return number


def _require_choice(value, name, choices):
    if value not in choices:
        raise RecipeError("{} must be one of {}, got {!r}".format(name, sorted(choices), value))
    return value


def validate_recipe(raw, reserved_labels):
    """Validate one raw mapping into (label, bundle); raises RecipeError.

    The returned bundle carries the same fourteen keys as a built-in
    QUICK_RECIPES entry, plus ``description``, ``custom``, and later
    ``source`` (added by the file loader).
    """
    if not isinstance(raw, dict):
        raise RecipeError("a recipe must be a mapping, got {}".format(type(raw).__name__))

    unknown = set(raw) - ALLOWED_KEYS
    if unknown:
        raise RecipeError("unknown recipe keys: {}".format(", ".join(sorted(unknown))))
    missing = REQUIRED_KEYS - set(raw)
    if missing:
        raise RecipeError("missing required keys: {}".format(", ".join(sorted(missing))))

    label = raw["label"]
    if not isinstance(label, str) or not label.strip():
        raise RecipeError("label must be a non-empty string")
    label = label.strip()
    if label in reserved_labels:
        raise RecipeError('label "{}" collides with an existing choice'.format(label))

    role = _require_choice(raw["role"], "role", ROLES)
    default_shape, default_global = recipe_tables.role_pull_defaults(role)

    guard = raw.get("guard", False)
    if not isinstance(guard, bool):
        raise RecipeError("guard must be true or false")

    cap = raw.get("cap")
    bundle = {
        "role": role,
        "treatment": _require_choice(raw.get("treatment", "normal"), "treatment", TREATMENTS),
        "color": _require_number(raw.get("color", 1.0), "color", *NUMERIC_RANGES["color"]),
        "detail": _require_number(raw.get("detail", 1.0), "detail", *NUMERIC_RANGES["detail"]),
        "study": _require_choice(str(raw.get("study", "stack")), "study", STUDY_CHOICES),
        "framing": _require_choice(raw.get("framing", "stack"), "framing", FRAMING_CHOICES),
        "subject": _require_choice(raw.get("subject", "recipe"), "subject", SUBJECT_CHOICES),
        "early": _require_number(raw.get("early", 1.0), "early", *NUMERIC_RANGES["early"]),
        "late": _require_number(raw.get("late", 1.0), "late", *NUMERIC_RANGES["late"]),
        "guard": guard,
        "cap": None if cap is None else _require_number(cap, "cap", *NUMERIC_RANGES["cap"]),
        "shape": _require_number(raw.get("shape", default_shape), "shape", *NUMERIC_RANGES["shape"]),
        "global": _require_number(raw.get("global", default_global), "global", *NUMERIC_RANGES["global"]),
    }

    layers = raw.get("layers")
    if layers is None:
        bundle["layers"] = recipe_tables.role_layer_pull_defaults(role)
    else:
        if not isinstance(layers, (list, tuple)) or len(layers) != LAYER_COUNT:
            raise RecipeError("layers must be a list of exactly {} numbers".format(LAYER_COUNT))
        bundle["layers"] = [
            _require_number(value, "layers[{}]".format(i), *LAYER_RANGE)
            for i, value in enumerate(layers)
        ]

    description = raw.get("description", "")
    if not isinstance(description, str):
        raise RecipeError("description must be a string")
    bundle["description"] = description.strip()
    bundle["custom"] = True
    return label, bundle


def _parse_file(path):
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        return json.loads(text)
    if yaml is None:
        raise RecipeError("PyYAML is not installed; use .json or install pyyaml")
    return yaml.safe_load(text)


def load_recipe_file(path, reserved_labels):
    """Load one recipe file; returns (label -> bundle dict, error strings).

    A file holds either a single recipe mapping or a pack:
    ``{"recipes": [recipe, recipe, ...]}``.
    """
    try:
        data = _parse_file(path)
    except RecipeError as error:
        return {}, ["{}: {}".format(path.name, error)]
    except Exception as error:
        return {}, ["{}: could not parse ({})".format(path.name, error)]

    if isinstance(data, dict) and "recipes" in data:
        extras = set(data) - {"recipes"}
        if extras:
            return {}, ["{}: a recipe pack may only contain the 'recipes' list (found: {})".format(
                path.name, ", ".join(sorted(extras)))]
        entries = data["recipes"]
        if not isinstance(entries, list):
            return {}, ["{}: 'recipes' must be a list".format(path.name)]
    elif isinstance(data, dict):
        entries = [data]
    else:
        return {}, ["{}: expected a recipe mapping or a mapping with a 'recipes' list".format(path.name)]

    loaded = {}
    errors = []
    for index, raw in enumerate(entries, start=1):
        try:
            label, bundle = validate_recipe(raw, frozenset(reserved_labels) | set(loaded))
        except RecipeError as error:
            errors.append("{}: recipe {}: {}".format(path.name, index, error))
            continue
        bundle["source"] = path.name
        loaded[label] = bundle
    return loaded, errors


def search_paths():
    """Directories scanned for recipe files, in priority order."""
    paths = [_PACK_RECIPE_DIR]
    try:
        import folder_paths  # ComfyUI host module; absent under tests.
        get_user_directory = getattr(folder_paths, "get_user_directory", None)
        if callable(get_user_directory):
            paths.append(Path(get_user_directory()) / "krea_reference" / "recipes")
    except Exception:
        pass
    paths.extend(Path(p) for p in EXTRA_SEARCH_PATHS)
    return paths


def _recipe_files():
    files = []
    for directory in search_paths():
        try:
            if not directory.is_dir():
                continue
            for path in sorted(directory.iterdir()):
                if path.name.startswith(("_", ".")):
                    continue  # documented convention for disabled templates
                if path.suffix.lower() in RECIPE_EXTENSIONS and path.is_file():
                    files.append(path)
        except OSError:
            continue
    return files


_last_errors = None


def refresh(reserved_labels):
    """Scan the search paths; returns (label -> bundle, error strings).

    Called by the card's INPUT_TYPES, so dropping a file and refreshing node
    definitions in ComfyUI picks it up without a restart. Errors are logged
    once per change, not once per scan.
    """
    global _last_errors
    recipes = {}
    errors = []
    for path in _recipe_files():
        loaded, file_errors = load_recipe_file(path, frozenset(reserved_labels) | set(recipes))
        errors.extend(file_errors)
        recipes.update(loaded)
    if errors and errors != _last_errors:
        for message in errors:
            _logger.warning("KG Krea V10 custom recipe skipped: %s", message)
    _last_errors = errors
    return recipes, errors


_warned_missing = set()


def warn_missing(label):
    """Warn once per label when a saved workflow references a removed recipe."""
    if label in _warned_missing:
        return
    _warned_missing.add(label)
    _logger.warning(
        'KG Krea V10: unknown "Use image for" value %r (custom recipe file removed or renamed?); '
        "falling back to the balanced recipe.", label,
    )
