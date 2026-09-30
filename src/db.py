"""SQLite: إنشاء الجداول (قسم 4.2)، تحميل CSV، وقراءة/كتابة."""

import csv
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from src.config import BAGHDAD_TZ, DB_PATH, SEALED_DIR, SYNTH_DIR

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


# ------------------------------------------------- قراءة/كتابة وقت التشغيل (قسم 9)
# هذه الدوال للـ API والديمو فقط: ما تلمس split=test إلا عبر evaluate --final.


def list_users(conn, split="dev") -> list:
    """المستخدمين مع عدد معاملاتهم وآخر وقت. الافتراضي dev بس (ما نكشف test)."""
    rows = conn.execute(
        "SELECT u.user_id, u.name, u.archetype, u.split, "
        "  (SELECT COUNT(*) FROM transactions t WHERE t.user_id = u.user_id) AS n_tx, "
        "  (SELECT MAX(t.ts) FROM transactions t WHERE t.user_id = u.user_id) AS last_ts "
        "FROM users u WHERE u.split = ? ORDER BY u.user_id",
        (split,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_user(conn, user_id) -> dict | None:
    row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


def user_history(conn, user_id, until=None) -> list:
    """معاملات المستخدم مرتبة بالوقت. until يفلتر اللي بعده (لو مرّرناه)."""
    sql = "SELECT * FROM transactions WHERE user_id = ?"
    params = [user_id]
    if until:
        sql += " AND ts < ?"
        params.append(until)
    return [dict(r) for r in conn.execute(sql + " ORDER BY ts, tx_id", params).fetchall()]


def last_balance(conn, user_id) -> int:
    """آخر رصيد معروف للمستخدم، حتى تشتغل قاعدة BALANCE_DRAIN بلا مدخل."""
    row = conn.execute(
        "SELECT balance_before_iqd FROM transactions WHERE user_id = ? "
        "ORDER BY ts DESC LIMIT 1",
        (user_id,),
    ).fetchone()
    return int(row[0]) if row and row[0] is not None else 0


def trusted_recipients(conn, user_id) -> list:
    rows = conn.execute(
        "SELECT recipient_id FROM trusted_recipients WHERE user_id = ? ORDER BY recipient_id",
        (user_id,),
    ).fetchall()
    return [r[0] for r in rows]


def add_trusted_recipient(conn, user_id, recipient_id, added_at=None) -> bool:
    """يضيف المستلم لقائمة الموثوقين. يرجع False إذا كان موجود أصلاً."""
    stamp = added_at or datetime.now(BAGHDAD_TZ).isoformat(timespec="seconds")
    cur = conn.execute(
        "INSERT OR IGNORE INTO trusted_recipients(user_id, recipient_id, added_at) VALUES (?, ?, ?)",
        (user_id, recipient_id, stamp),
    )
    conn.commit()
    return cur.rowcount > 0


def log_assessment(conn, tx_id, user_id, assessment, coaching, created_at=None) -> int:
    """يكتب صف بجدول decision_log (قسم 9) ويرجّع log_id."""
    stamp = created_at or datetime.now(BAGHDAD_TZ).isoformat(timespec="seconds")
    cur = conn.execute(
        "INSERT INTO decision_log(tx_id, user_id, created_at, risk_score, decision, "
        "reasons_json, matched_pattern, coaching_message, coaching_source, rules_version) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            tx_id,
            user_id,
            stamp,
            int(assessment["score"]),
            assessment["decision"],
            json.dumps(assessment["reasons"], ensure_ascii=False),
            assessment.get("matched_pattern"),
            coaching.get("message"),
            coaching.get("source"),
            assessment.get("rules_version"),
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def set_choice(conn, tx_id, choice, at=None) -> dict | None:
    """يحدّث نفس صف السجل بقرار المستخدم. يرجع الصف أو None إذا ما موجود."""
    stamp = at or datetime.now(BAGHDAD_TZ).isoformat(timespec="seconds")
    cur = conn.execute(
        "UPDATE decision_log SET user_choice = ?, choice_at = ? WHERE tx_id = ?",
        (choice, stamp, tx_id),
    )
    conn.commit()
    if cur.rowcount == 0:
        return None
    return get_log_row(conn, tx_id)


def get_log_row(conn, tx_id) -> dict | None:
    row = conn.execute(
        "SELECT * FROM decision_log WHERE tx_id = ? ORDER BY log_id DESC LIMIT 1", (tx_id,)
    ).fetchone()
    return dict(row) if row else None


def read_decision_log(conn, limit=100, offset=0, decision=None, user_id=None) -> list:
    sql = "SELECT * FROM decision_log WHERE 1 = 1"
    params = []
    if decision:
        sql += " AND decision = ?"
        params.append(decision)
    if user_id:
        sql += " AND user_id = ?"
        params.append(user_id)
    sql += " ORDER BY log_id DESC LIMIT ? OFFSET ?"
    params += [int(limit), int(offset)]
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def all_decisions(conn) -> list:
    """كل صفوف السجل للتصدير (9)."""
    return [dict(r) for r in conn.execute("SELECT * FROM decision_log ORDER BY log_id").fetchall()]


def count_decisions(conn) -> int:
    return int(conn.execute("SELECT COUNT(*) FROM decision_log").fetchone()[0])



if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "dev")
