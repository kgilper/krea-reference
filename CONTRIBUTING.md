# Contributing

Thanks for helping improve Krea Reference.

## Development Setup

1. Clone the repo.
2. Install or use an existing ComfyUI environment.
3. Run the local contract tests before submitting changes:

```bash
python -m unittest discover -s tests -p "test_*.py" -v
python -m compileall -q kg_krea_v9 __init__.py
```

## Pull Requests

- Keep pull requests focused on one behavior or documentation change.
- Preserve node keys and widget labels unless the change is intentionally breaking and documented.
- Do not commit model weights, generated outputs, private images, local ComfyUI paths, or agent skill folders.
- If a workflow example changes, keep it portable and avoid adding extra workflow systems unless the example is specifically about that feature.
- Update README/docs/tests when user-facing behavior changes.

## Example Images

Example images in `example_assets/` must be original assets created for this repo, or clearly licensed for redistribution. Do not add user/client/private photos.
