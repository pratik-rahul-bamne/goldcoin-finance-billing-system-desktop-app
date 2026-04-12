import sqlite3
import tempfile
from pathlib import Path
import pandas as pd

import pytest

from backup.backup_service import create_backup
from backup.restore_service import restore_from_excel


def create_sample_db(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute('CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT, mobile TEXT);')
    cur.execute('CREATE TABLE payments (id INTEGER PRIMARY KEY, customer_id INTEGER, amount REAL, date TEXT);')
    cur.execute("INSERT INTO customers (id, name, mobile) VALUES (1, 'Alice', '9999999999')")
    conn.commit()
    conn.close()


def read_sheet_names(xlsx_path):
    xls = pd.ExcelFile(xlsx_path)
    return xls.sheet_names


def read_table_count(db_path, table):
    conn = sqlite3.connect(db_path)
    cnt = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    conn.close()
    return cnt


def test_create_backup_and_sheet_names(tmp_path):
    db_path = tmp_path / 'test.db'
    create_sample_db(db_path)

    backup_dir = tmp_path / 'backup_files'
    log_file = tmp_path / 'logs' / 'backup_restore.log'

    result = create_backup(str(db_path), destination='local', backup_dir=backup_dir, log_file=log_file)
    assert result['status'] == 'success'

    backup_path = Path(result['path'])
    assert backup_path.exists()

    sheet_names = read_sheet_names(backup_path)
    assert 'customers' in sheet_names
    assert 'payments' in sheet_names

    assert read_table_count(db_path, 'customers') == 1


def test_restore_append_and_replace(tmp_path):
    db_path = tmp_path / 'test.db'
    create_sample_db(db_path)

    backup_dir = tmp_path / 'backup_files'
    log_file = tmp_path / 'logs' / 'backup_restore.log'

    # initial backup has one Alice
    b = create_backup(str(db_path), destination='local', backup_dir=backup_dir, log_file=log_file)
    assert b['status'] == 'success'

    # add Bob after backup
    conn = sqlite3.connect(db_path)
    conn.execute("INSERT INTO customers (id, name, mobile) VALUES (2, 'Bob', '8888888888')")
    conn.commit()
    conn.close()
    assert read_table_count(db_path, 'customers') == 2

    # append mode: existing ids should be ignored, so count stays 2
    restore_from_excel(b['path'], str(db_path), mode='append')
    assert read_table_count(db_path, 'customers') == 2

    # replace mode: should reset to backup data (1 row)
    restore_from_excel(b['path'], str(db_path), mode='replace')
    assert read_table_count(db_path, 'customers') == 1
