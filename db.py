import sqlite3
from pathlib import Path
from datetime import datetime, timedelta, timezone

DB_PATH = Path(__file__).resolve().parent.parent.parent / "bdtrader.db"

def _connect():
    return sqlite3.connect(DB_PATH)

def init_db():
    DB_PATH.touch(exist_ok=True)
    con = _connect()
    cur = con.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users(
        user_id     INTEGER PRIMARY KEY,
        first_seen  TEXT NOT NULL,
        country     TEXT,
        tz          TEXT,
        is_vip      INTEGER DEFAULT 0,
        vip_expiry  TEXT
    );
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS usage_logs(
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id     INTEGER NOT NULL,
        used_at     TEXT NOT NULL
    );
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS signals(
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id     INTEGER NOT NULL,
        pair        TEXT,
        timeframe   TEXT,
        sent_at     TEXT NOT NULL,
        confidence  INTEGER,
        risky       INTEGER,
        message     TEXT
    );
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS outcomes(
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        signal_id   INTEGER NOT NULL,
        result      TEXT,     -- WIN/LOSS/NA
        note        TEXT
    );
    """)
    con.commit()
    con.close()

def now_utc_iso():
    return datetime.now(timezone.utc).isoformat()

def get_or_create_user(user_id: int):
    con = _connect(); cur = con.cursor()
    cur.execute("SELECT user_id, first_seen, is_vip, vip_expiry FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    if not row:
        cur.execute("INSERT INTO users(user_id, first_seen) VALUES (?,?)", (user_id, now_utc_iso()))
        con.commit()
    con.close()

def set_country(user_id: int, country: str, tz: str | None = None):
    con = _connect(); cur = con.cursor()
    cur.execute("UPDATE users SET country=?, tz=? WHERE user_id=?", (country, tz, user_id))
    con.commit(); con.close()

def is_vip(user_id: int) -> bool:
    con = _connect(); cur = con.cursor()
    cur.execute("SELECT is_vip, vip_expiry FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    con.close()
    if not row:
        return False
    isvip, expiry = row
    if not isvip:
        return False
    if expiry:
        try:
            exp = datetime.fromisoformat(expiry)
            if datetime.now(timezone.utc) > exp:
                # expired -> auto downgrade
                con = _connect(); cur = con.cursor()
                cur.execute("UPDATE users SET is_vip=0, vip_expiry=NULL WHERE user_id=?", (user_id,))
                con.commit(); con.close()
                return False
        except Exception:
            return True
    return True

def set_vip(user_id: int, days: int):
    con = _connect(); cur = con.cursor()
    exp = datetime.now(timezone.utc) + timedelta(days=max(1, days))
    cur.execute("""
        INSERT INTO users(user_id, first_seen, is_vip, vip_expiry)
        VALUES (?,?,1,?)
        ON CONFLICT(user_id) DO UPDATE SET is_vip=1, vip_expiry=excluded.vip_expiry
    """, (user_id, now_utc_iso(), exp.isoformat()))
    con.commit(); con.close()

def remove_vip(user_id: int):
    con = _connect(); cur = con.cursor()
    cur.execute("UPDATE users SET is_vip=0, vip_expiry=NULL WHERE user_id=?", (user_id,))
    con.commit(); con.close()

def record_usage(user_id: int):
    con = _connect(); cur = con.cursor()
    cur.execute("INSERT INTO usage_logs(user_id, used_at) VALUES (?,?)", (user_id, now_utc_iso()))
    con.commit(); con.close()

def count_usage_today(user_id: int) -> int:
    # UTC দিন ধরে (পরবর্তীতে দেশ/টাইমজোন অ্যাডজাস্ট করা যাবে)
    today = datetime.utcnow().date().isoformat()
    con = _connect(); cur = con.cursor()
    cur.execute("""
        SELECT COUNT(*) FROM usage_logs
        WHERE user_id=? AND substr(used_at,1,10)=?
    """, (user_id, today))
    n = cur.fetchone()[0]
    con.close()
    return int(n)

def get_first_seen_date(user_id: int):
    con = _connect(); cur = con.cursor()
    cur.execute("SELECT first_seen FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone(); con.close()
    if not row or not row[0]:
        return None
    try:
        dt = datetime.fromisoformat(row[0])
        return dt.date()
    except Exception:
        return None

def log_signal(user_id: int, pair: str, tf: str, confidence: int, risky: bool, message: str):
    con = _connect(); cur = con.cursor()
    cur.execute("""
        INSERT INTO signals(user_id, pair, timeframe, sent_at, confidence, risky, message)
        VALUES (?,?,?,?,?,?,?)
    """, (user_id, pair, tf, now_utc_iso(), int(confidence), 1 if risky else 0, message))
    con.commit(); con.close()

def list_vip():
    con = _connect(); cur = con.cursor()
    cur.execute("SELECT user_id, vip_expiry FROM users WHERE is_vip=1")
    rows = cur.fetchall(); con.close()
    return rows

def vip_stats():
    con = _connect(); cur = con.cursor()
    cur.execute("""
        SELECT COUNT(*) FROM users WHERE is_vip=1
    """)
    vip_count = cur.fetchone()[0]
    cur.execute("""
        SELECT COUNT(*) FROM users
    """)
    total = cur.fetchone()[0]
    con.close()
    return {"vip": vip_count, "total": total}
