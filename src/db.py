"""SQLite: إنشاء الجداول (قسم 4.2)، تحميل CSV، وقراءة/كتابة."""

import csv
import sqlite3
import sys
from pathlib import Path

from src.config import DB_PATH, SEALED_DIR, SYNTH_DIR

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  user_id TEXT PRIMARY KEY, name TEXT, archetype TEXT,
  split TEXT            -- 'dev' أو 'test'
);

CREATE TABLE IF NOT EXISTS transactions(
  tx_id TEXT PRIMARY KEY, user_id TEXT, ts TEXT, amount_iqd INTEGER,
  balance_before_iqd INTEGER, tx_type TEXT, recipient_id TEXT,
  recipient_age_days INTEGER, note TEXT, context_message TEXT,
  is_scam INTEGER, scam_type TEXT, case_id TEXT
);

CREATE TABLE IF NOT EXISTS decision_log(
  log_id INTEGER PRIMARY KEY AUTOINCREMENT,
  tx_id TEXT, user_id TEXT, created_at TEXT,
  risk_score INTEGER, decision TEXT,       -- allow / warn / hold
  reasons_json TEXT, matched_pattern TEXT,
  coaching_message TEXT, coaching_source TEXT,  -- template / llm
  user_choice TEXT,                        -- continue / cancel / no_response
  choice_at TEXT, rules_version TEXT
);

CREATE TABLE IF NOT EXISTS trusted_recipients(user_id TEXT, recipient_id TEXT, added_at TEXT,
  PRIMARY KEY(user_id, recipient_id));
"""


def get_connection(db_path=None):
    # نفتح الاتصال بوضع الصفوف حتى نرجّع dict بدل tuple
    path = Path(db_path) if db_path else DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path=None):
    # ينشئ ملف القاعدة والجداول إذا ما موجودة (idempotent)
    conn = get_connection(db_path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


USER_FIELDS = ("user_id", "name", "archetype", "split")
TX_FIELDS = ("tx_id", "user_id", "ts", "amount_iqd", "balance_before_iqd", "tx_type",
             "recipient_id", "recipient_age_days", "note", "context_message",
             "is_scam", "scam_type", "case_id")
INT_TX_FIELDS = ("amount_iqd", "balance_before_iqd", "recipient_age_days", "is_scam")


def read_csv(path) -> list:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_csvs(db_path=None, split="dev") -> dict:
    """يحمّل CSV إلى الجداول (قسم 4).

    split='dev'  -> data/synthetic/ (الملف الوحيد المسموح بقراءته للكود)
    split='test' -> data/test_sealed/، ويستخدمه evaluate --final فقط حسب AGENTS.md
    """
    if split not in ("dev", "test"):
        raise ValueError(f"split لازم dev أو test، جاي {split!r}")
    source = SYNTH_DIR if split == "dev" else SEALED_DIR
    users = read_csv(source / "users.csv")
    txs = read_csv(source / "transactions.csv")
    keep = {"dev": "dev", "test": "test"}[split]

    users = [u for u in users if u["split"] == keep]
    txs = [t for t in txs if t["user_id"] in {u["user_id"] for u in users}]
    for t in txs:
        for k in INT_TX_FIELDS:
            t[k] = int(t[k] or 0)
        for k in ("note", "context_message", "scam_type", "case_id"):
            t[k] = t[k] or None

    init_db(db_path)
    conn = get_connection(db_path)
    try:
        # نمسح صفوف هذه الجه�� أول: INSERT OR REPLACE ما يحذف المعاملات القديمة
        # اللي اختفت من الملف بعد إعادة التوليد، فتبقى بالجداول زوائد
        placeholders = ",".join("?" * len(users))
        ids = [u["user_id"] for u in users]
        conn.execute(f"DELETE FROM transactions WHERE user_id IN ({placeholders})", ids)
        conn.execute(f"DELETE FROM users WHERE user_id IN ({placeholders})", ids)
        conn.executemany(
            f"INSERT OR REPLACE INTO users({','.join(USER_FIELDS)}) "
            f"VALUES({','.join('?' * len(USER_FIELDS))})",
            [[u[k] for k in USER_FIELDS] for u in users],
        )
        conn.executemany(
            f"INSERT OR REPLACE INTO transactions({','.join(TX_FIELDS)}) "
            f"VALUES({','.join('?' * len(TX_FIELDS))})",
            [[t[k] for k in TX_FIELDS] for t in txs],
        )
        conn.commit()
        counts = {
            "users": conn.execute("SELECT COUNT(*) FROM users").fetchone()[0],
            "transactions": conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0],
        }
    finally:
        conn.close()
    return counts


def main(split="dev"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    print(f"تم إنشاء الجداول في: {DB_PATH}")
    counts = load_csvs(split=split)
    print(f"تم تحميل {split}: {counts['users']} مستخدم و {counts['transactions']} معاملة")
    print("decision_log و trusted_recipients يتعبونون وقت التشغيل (فارغين الحين)")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "dev")
