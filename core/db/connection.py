"""Database connection helpers."""
import sqlite3
from pathlib import Path

DB_FILE = Path("data/lingualearn.db")
DB_FILE.parent.mkdir(exist_ok=True)

def get_db():
    """获取数据库连接"""
    conn = sqlite3.connect(str(DB_FILE))
    conn.row_factory = sqlite3.Row
    return conn

