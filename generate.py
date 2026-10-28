"""Write every task's items to data/<task>/: items.jsonl, shared.json and any generated files.

    python benchmarks/cost-per-task/generate.py            # all tasks
    python benchmarks/cost-per-task/generate.py --check    # regenerate in memory and fail if data/ differs

Receipt PNGs are the exception: they are rendered once, committed, and checked against data/manifest.json.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bench import registry  # noqa: E402

DATA = Path(__file__).resolve().parent / "data"


def render(task) -> dict[str, bytes]:
    items, shared = registry.generate(task)
    files = dict(shared.pop("files", {}))
    out = {path: content for path, content in files.items()}
    out["items.jsonl"] = "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in items).encode()
    out["shared.json"] = (json.dumps(shared, ensure_ascii=False, sort_keys=True, indent=1) + "\n").encode()
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if data/ is not what the generators produce")
    parser.add_argument("--task", choices=sorted(registry.BY_ID))
    parser.add_argument("--rerender-images", action="store_true", help="overwrite the committed PNGs (changes their hashes)")
    args = parser.parse_args()
    tasks = [registry.BY_ID[args.task]] if args.task else registry.ALL_TASKS
    recorded = json.loads((DATA / "manifest.json").read_text())["files"] if (DATA / "manifest.json").exists() else {}
    manifest = {}
    stale = []
    for task in tasks:
        folder = DATA / task.TASK_ID
        for name, content in sorted(render(task).items()):
            target = folder / name
            key = f"{task.TASK_ID}/{name}"
            if name.endswith(".png"):
                # Pillow's text rendering and PNG encoding differ slightly between platforms, so images are
                # rendered once and committed; they are checked against the manifest, not re-rendered.
                if not args.check and (args.rerender_images or not target.exists()):
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(content)
                actual = hashlib.sha256(target.read_bytes()).hexdigest() if target.exists() else None
                manifest[key] = actual
                if args.check and (actual is None or actual != recorded.get(key)):
                    stale.append(str(target.relative_to(DATA)))
                continue
            digest = hashlib.sha256(content).hexdigest()
            manifest[key] = digest
            if args.check:
                if not target.exists() or hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                    stale.append(str(target.relative_to(DATA)))
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
    if args.check:
        if stale:
            print("stale or missing generated files:\n  " + "\n  ".join(stale))
            return 1
        print(f"data/ matches the generators ({len(manifest)} files)")
        return 0
    if not args.task:
        (DATA / "manifest.json").write_text(json.dumps({"seed": registry.SEED, "files": manifest}, indent=1, sort_keys=True) + "\n")
    print(f"wrote {len(manifest)} files under {DATA}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
