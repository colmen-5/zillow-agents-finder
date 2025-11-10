thonimport json
import logging
import os
from typing import Any, Dict

def setup_logging(level: str = "INFO") -> None:
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )

def ensure_dir_for_file(path: str) -> None:
    directory = os.path.dirname(os.path.abspath(path))
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)

def load_json_file(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json_file(path: str, data: Any) -> None:
    ensure_dir_for_file(path)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def load_settings(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Settings file not found: {path}")
    return load_json_file(path)

def try_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(str(value).strip().replace(",", ""))
    except (TypeError, ValueError):
        return None

def try_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None

def normalize_whitespace(text: str | None) -> str | None:
    if text is None:
        return None
    return " ".join(str(text).split())