"""建表：用户、采集条目、子分类开关、采集日志"""
from .database import get_conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_admin INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subcategory_id TEXT NOT NULL,
            title TEXT NOT NULL,
            url TEXT NOT NULL,
            description TEXT DEFAULT '',
            source_name TEXT DEFAULT '',
            stars INTEGER DEFAULT NULL,
            published_at TEXT DEFAULT '',
            collected_at TEXT NOT NULL,
            is_manual INTEGER NOT NULL DEFAULT 0
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_items_sub ON items(subcategory_id)")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS subcat_state (
            subcategory_id TEXT PRIMARY KEY,
            enabled INTEGER NOT NULL DEFAULT 1
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS collect_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_name TEXT NOT NULL,
            status TEXT NOT NULL,
            count INTEGER NOT NULL DEFAULT 0,
            message TEXT DEFAULT '',
            started_at TEXT NOT NULL,
            finished_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()
