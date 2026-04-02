"""Persistent paths next to the executable (PyInstaller) or project root (dev)."""

import os
import sys


def data_path(filename: str) -> str:
    """Absolute path for persistent data files.

    In frozen (PyInstaller) mode we store under %LOCALAPPDATA% (user-writable)
    to avoid permission issues when installing to Program Files.
    """
    if getattr(sys, "frozen", False):
        base = os.environ.get("LOCALAPPDATA") or os.path.abspath(".")
        app_dir = os.path.join(base, "GoldCoinBilling")
        os.makedirs(app_dir, exist_ok=True)
        return os.path.join(app_dir, filename)
    return os.path.join(os.path.abspath("."), filename)


def db_path() -> str:
    return data_path("goldcoin_billing.db")


def backup_dir() -> str:
    d = data_path("backup_files")
    os.makedirs(d, exist_ok=True)
    return d


def log_dir() -> str:
    d = data_path("logs")
    os.makedirs(d, exist_ok=True)
    return d


def backup_log_file() -> str:
    return os.path.join(log_dir(), "backup.log")
