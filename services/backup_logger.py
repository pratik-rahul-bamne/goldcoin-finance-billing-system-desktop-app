"""Append-only backup / restore activity log."""

from datetime import datetime
from pathlib import Path


def _timestamp() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def log_info(log_path: str, message: str) -> None:
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"[{_timestamp()}] INFO {message}\n")


def log_error(log_path: str, message: str) -> None:
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"[{_timestamp()}] ERROR {message}\n")
