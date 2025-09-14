#!/usr/bin/env python3
import json, sqlite3, pathlib, time, os, tempfile, shutil

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DB    = ROOT / "db" / "spotify.db"
DB.parent.mkdir(parents=True, exist_ok=True)

def load_jsons():
    paths = sorted(DATA.glob("StreamingHistory_music_*.json"))
    rows = []
    for p in paths:
        with open(p, "r", encoding="utf-8") as f:
            rows.extend(json.load(f))
    if not rows:
        raise SystemExit("No streaming history files found in data/")
    return rows

def connect(path: pathlib.Path):
    # Wait up to 30s for any other process to finish
    conn = sqlite3.connect(path, timeout=30, isolation_level=None)
    cur = conn.cursor()
    cur.execute("PRAGMA busy_timeout=30000;")     # retry if locked
    cur.execute("PRAGMA journal_mode=DELETE;")    # simpler journal, fewer side files
    cur.execute("PRAGMA synchronous=NORMAL;")
    return conn, cur

def main():
    rows = load_jsons()

    # 1) Build DB in a temp file to avoid fighting an open handle on spotify.db
    tmp_dir = tempfile.mkdtemp(prefix="spotify_db_")
    tmp_db  = pathlib.Path(tmp_dir) / "spotify_tmp.db"

    conn, cur = connect(tmp_db)
    try:
        cur.execute("BEGIN;")
        cur.executescript("""
        DROP TABLE IF EXISTS listens;
        CREATE TABLE listens(
            endTime    TEXT    NOT NULL,
            artistName TEXT    NOT NULL,
            trackName  TEXT    NOT NULL,
            msPlayed   INTEGER NOT NULL
        );
        """)
        cur.executemany(
            "INSERT INTO listens(endTime, artistName, trackName, msPlayed) VALUES (?,?,?,?)",
            [(r["endTime"], r["artistName"], r["trackName"], int(r["msPlayed"])) for r in rows]
        )
        cur.execute("COMMIT;")
    except Exception:
        try: cur.execute("ROLLBACK;")
        except Exception: pass
        conn.close()
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise
    finally:
        conn.close()

    # 2) Atomically replace old DB (even if some app still has it open)
    #    Remove sidecar files first to avoid mismatched -wal/-shm.
    for suffix in ["", "-wal", "-shm"]:
        p = pathlib.Path(str(DB) + suffix)
        try: p.unlink()
        except FileNotFoundError: pass
        except PermissionError: pass

    os.replace(tmp_db, DB)  # atomic on same filesystem
    shutil.rmtree(tmp_dir, ignore_errors=True)
    print(f"Loaded {len(rows)} rows into {DB}")

if __name__ == "__main__":
    main()
