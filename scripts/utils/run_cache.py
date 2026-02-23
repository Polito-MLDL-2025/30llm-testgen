import hashlib
import json
from pathlib import Path
from typing import Any


def _sanitize_name(value: str) -> str:
    return value.replace("/", "_").replace(":", "_").replace(" ", "_")


def build_cache_path(output_dir: Path, script_id: str, config_tag: str, args_signature: dict[str, Any]) -> Path:
    payload = {
        "script_id": script_id,
        "config_tag": config_tag,
        "args_signature": args_signature,
    }
    digest = hashlib.sha1(
        json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:12]
    safe_tag = _sanitize_name(config_tag)
    return output_dir / f".cache_{script_id}_{safe_tag}_{digest}.json"


def load_run_cache(cache_path: Path) -> dict[int, dict[str, Any]]:
    if not cache_path.exists():
        return {}

    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception:
        return {}

    rows = data.get("rows", [])
    if not isinstance(rows, list):
        return {}

    rows_by_run: dict[int, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        run_value = row.get("run")
        if isinstance(run_value, int) and run_value > 0:
            rows_by_run[run_value] = row
    return rows_by_run


def save_run_cache(cache_path: Path, rows_by_run: dict[int, dict[str, Any]]) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    ordered_rows = [rows_by_run[idx] for idx in sorted(rows_by_run.keys())]
    payload = {
        "version": 1,
        "rows": ordered_rows,
    }

    tmp_path = cache_path.with_suffix(cache_path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp_path.replace(cache_path)
