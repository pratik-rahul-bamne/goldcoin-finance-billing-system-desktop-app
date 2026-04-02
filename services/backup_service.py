"""Export SQLite tables to timestamped .xlsx (one sheet per table)."""

from __future__ import annotations

import os
import re
import sqlite3
import time
from datetime import datetime

from openpyxl import Workbook

from services.backup_logger import log_error, log_info
from services.paths import backup_log_file

# Order matches FK dependencies for documentation; export reads independently.
TABLES: tuple[str, ...] = (
    "settings",
    "service_catalog",
    "customers",
    "services",
    "payments",
)

_SHEET_INVALID = re.compile(r"[][*?:/\\]")


def _safe_sheet_title(name: str) -> str:
    s = _SHEET_INVALID.sub("_", name)
    return (s[:31] if len(s) > 31 else s) or "sheet"


def _table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    cur = conn.execute(f'PRAGMA table_info("{table}")')
    return [row[1] for row in cur.fetchall()]


def export_database(
    db_path: str,
    backup_root: str,
    log_path: str | None = None,
) -> tuple[str | None, str | None]:
    """
    Write all TABLES to a new workbook. Returns (absolute_path, None) on success,
    or (None, error_message) on failure.
    """
    log_path = log_path or backup_log_file()
    ts = datetime.now().strftime("%Y_%m_%d_%H%M%S")
    filename = f"backup_{ts}.xlsx"
    out_path = os.path.join(backup_root, filename)

    wb = Workbook()
    default = wb.active
    if default:
        wb.remove(default)

    counts: list[str] = []
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            for table in TABLES:
                if not _table_exists(conn, table):
                    raise RuntimeError(f"Missing table: {table}")
                cols = _table_columns(conn, table)
                ws = wb.create_sheet(title=_safe_sheet_title(table))
                ws.append(cols)
                cur = conn.execute(f'SELECT * FROM "{table}"')
                rows = cur.fetchall()
                for r in rows:
                    ws.append([r[c] for c in cols])
                counts.append(f"{table}={len(rows)}")
        finally:
            conn.close()
        wb.save(out_path)
    except Exception as e:
        log_error(log_path, f"Backup failed: {e}")
        if os.path.isfile(out_path):
            try:
                os.remove(out_path)
            except OSError:
                pass
        return None, str(e)

    log_info(
        log_path,
        f"Backup OK file={out_path} " + " ".join(counts),
    )
    return out_path, None


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def list_backup_files(backup_root: str, limit: int = 40) -> list[dict]:
    """Newest-first file listing for UI history."""
    if not os.path.isdir(backup_root):
        return []
    items: list[tuple[float, dict]] = []
    for name in os.listdir(backup_root):
        if not name.lower().endswith(".xlsx"):
            continue
        path = os.path.join(backup_root, name)
        if not os.path.isfile(path):
            continue
        try:
            st = os.stat(path)
        except OSError:
            continue
        items.append(
            (
                st.st_mtime,
                {
                    "name": name,
                    "path": path,
                    "size_bytes": st.st_size,
                    "modified": datetime.fromtimestamp(st.st_mtime).isoformat(
                        sep=" ", timespec="seconds"
                    ),
                },
            )
        )
    items.sort(key=lambda x: x[0], reverse=True)
    return [d for _, d in items[:limit]]


def cleanup_old_backups(
    backup_root: str,
    log_path: str | None = None,
    max_age_days: int = 90,
    keep_minimum: int = 10,
) -> int:
    """
    Delete .xlsx backups older than max_age_days, but never go below keep_minimum files.
    Returns number of files removed.
    """
    log_path = log_path or backup_log_file()
    files = list_backup_files(backup_root, limit=5000)
    if len(files) <= keep_minimum:
        return 0
    cutoff = time.time() - max_age_days * 86400
    removed = 0
    # Oldest first among those past retention
    by_age = sorted(
        [(os.path.getmtime(f["path"]), f) for f in files],
        key=lambda x: x[0],
    )
    survivors = len(files)
    for mtime, info in by_age:
        if survivors <= keep_minimum:
            break
        if mtime >= cutoff:
            continue
        try:
            os.remove(info["path"])
            removed += 1
            survivors -= 1
            log_info(log_path, f"Retention removed old backup {info['name']}")
        except OSError as e:
            log_error(log_path, f"Retention delete failed {info['name']}: {e}")
    return removed


def run_scheduled_monthly_backup(db_path: str, backup_root: str) -> None:
    """Called by scheduler: export + light retention pass."""
    log_path = backup_log_file()
    path, err = export_database(db_path, backup_root, log_path)
    if err:
        return
    try:
        cleanup_old_backups(backup_root, log_path, max_age_days=90, keep_minimum=10)
    except Exception as e:
        log_error(log_path, f"Scheduled retention cleanup error: {e}")
