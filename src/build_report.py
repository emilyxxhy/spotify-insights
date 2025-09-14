#!/usr/bin/env python3
import sqlite3, pathlib, pandas as pd, numpy as np
import matplotlib.pyplot as plt
from jinja2 import Template

ROOT = pathlib.Path(__file__).resolve().parents[1]
DB = ROOT / "db" / "spotify.db"
OUT_DIR = ROOT / "outputs"
IMG_DIR = OUT_DIR / "report_images"
CACHE_DIR = ROOT / "cache"
OUT_DIR.mkdir(parents=True, exist_ok=True); IMG_DIR.mkdir(parents=True, exist_ok=True)

def q(con, sql, params=None):
    return pd.read_sql_query(sql, con, params=params)

def fmt_table(df, max_rows=10):
    if df.empty: return "_(no data)_"
    return df.head(max_rows).to_markdown(index=False)

def plot_monthly(con):
    df = q(con, """
        SELECT strftime('%Y-%m', endTime) AS month,
               SUM(msPlayed)/3600000.0 AS hours
        FROM listens GROUP BY month ORDER BY month;
    """)
    if df.empty: return
    plt.figure(figsize=(10,3))
    plt.plot(df["month"], df["hours"], marker="o")
    plt.xticks(rotation=45, ha="right")
    plt.xlabel("Month"); plt.ylabel("Hours"); plt.title("Monthly Listening Hours")
    plt.tight_layout(); plt.savefig(IMG_DIR/"monthly_hours.png", dpi=150); plt.close()

def plot_by_hour(con):
    df = q(con, """
        SELECT CAST(strftime('%H', endTime) AS INTEGER) AS hour,
               SUM(msPlayed)/3600000.0 AS hours
        FROM listens GROUP BY hour ORDER BY hour;
    """)
    if df.empty: return [], ""
    plt.figure(figsize=(8,3))
    plt.plot(df["hour"], df["hours"], marker="o")
    plt.xlabel("Hour"); plt.ylabel("Hours"); plt.title("By Hour of Day")
    plt.tight_layout(); plt.savefig(IMG_DIR/"by_hour.png", dpi=150); plt.close()
    top = df.sort_values("hours", ascending=False).head(3)["hour"].tolist()
    label = ", ".join(f"{h}h" for h in top)
    return top, label

def plot_by_weekday(con):
    df = q(con, """
        SELECT CASE strftime('%w', endTime)
            WHEN '0' THEN 'Sun' WHEN '1' THEN 'Mon' WHEN '2' THEN 'Tue'
            WHEN '3' THEN 'Wed' WHEN '4' THEN 'Thu' WHEN '5' THEN 'Fri'
            WHEN '6' THEN 'Sat' END AS weekday,
            SUM(msPlayed)/3600000.0 AS hours
        FROM listens GROUP BY strftime('%w', endTime) ORDER BY strftime('%w', endTime);
    """)
    if df.empty: return ""
    plt.figure(figsize=(7,3))
    plt.bar(df["weekday"], df["hours"])
    plt.xlabel("Weekday"); plt.ylabel("Hours"); plt.title("By Weekday")
    plt.tight_layout(); plt.savefig(IMG_DIR/"by_weekday.png", dpi=150); plt.close()
    top = df.sort_values("hours", ascending=False).head(3)["weekday"].tolist()
    return ", ".join(top)

def compute_hhi(con):
    df = q(con, "SELECT artistName, SUM(msPlayed) AS ms FROM listens GROUP BY artistName")
    if df.empty: return 0.0, "no data"
    total = df["ms"].sum()
    shares = (df["ms"] / total)**2
    hhi = shares.sum()
    label = "Explorer" if hhi < 0.07 else ("Balanced" if hhi < 0.12 else "Loyalist")
    return float(hhi), label

def top_artists(con):
    return q(con, """
        SELECT artistName, ROUND(SUM(msPlayed)/3600000.0, 2) AS hours_listened, COUNT(*) AS plays
        FROM listens GROUP BY artistName ORDER BY hours_listened DESC, plays DESC LIMIT 10;
    """)

def top_tracks(con):
    return q(con, """
        SELECT trackName, artistName, ROUND(SUM(msPlayed)/3600000.0, 2) AS hours_listened, COUNT(*) AS plays
        FROM listens GROUP BY trackName, artistName ORDER BY hours_listened DESC, plays DESC LIMIT 10;
    """)

def repeat_metrics(con):
    a = q(con, "SELECT COUNT(*) AS plays FROM listens").iloc[0]["plays"]
    b = q(con, "SELECT COUNT(DISTINCT trackName) AS uniq FROM listens").iloc[0]["uniq"]
    avg = round(a / b, 2) if b else 0
    return a, b, avg

def skip_metrics(con):
    df = q(con, """
        SELECT
          COUNT(*) AS total_plays,
          SUM(CASE WHEN msPlayed < 30000 THEN 1 ELSE 0 END) AS plays_lt_30s,
          ROUND(100.0 * SUM(CASE WHEN msPlayed < 30000 THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_lt_30s,
          SUM(CASE WHEN msPlayed < 60000 THEN 1 ELSE 0 END) AS plays_lt_60s,
          ROUND(100.0 * SUM(CASE WHEN msPlayed < 60000 THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_lt_60s
        FROM listens;
    """).iloc[0]
    return float(df["pct_lt_30s"]), float(df["pct_lt_60s"])

def binges(con):
    return q(con, """
        WITH month_artist AS (
          SELECT strftime('%Y-%m', endTime) AS month, artistName, SUM(msPlayed) AS ms_month_artist
          FROM listens GROUP BY month, artistName
        ),
        month_total AS (
          SELECT month, SUM(ms_month_artist) AS ms_month_total FROM month_artist GROUP BY month
        )
        SELECT m.month, m.artistName, ROUND(100.0 * m.ms_month_artist / t.ms_month_total, 1) AS month_share_pct
        FROM month_artist m
        JOIN month_total t USING(month)
        WHERE m.ms_month_artist >= 30*60*1000
        ORDER BY m.month, month_share_pct DESC;
    """)

def discovery(con):
    df = q(con, """
        WITH first_seen AS (
          SELECT artistName, MIN(date(endTime)) AS first_date FROM listens GROUP BY artistName
        ),
        calendar AS (SELECT DISTINCT date(endTime) AS d FROM listens),
        daily AS (
          SELECT c.d, COALESCE(SUM(CASE WHEN f.first_date = c.d THEN 1 ELSE 0 END),0) AS new_artists
          FROM calendar c LEFT JOIN first_seen f ON f.first_date = c.d
          GROUP BY c.d
        )
        SELECT d AS date, new_artists,
               SUM(new_artists) OVER (ORDER BY d ROWS UNBOUNDED PRECEDING) AS cumulative_artists
        FROM daily ORDER BY date;
    """)
    if df.empty: return df
    plt.figure(figsize=(10,3))
    plt.plot(df["date"], df["cumulative_artists"], marker="o")
    plt.xlabel("Date"); plt.ylabel("Cumulative Artists"); plt.title("Discovery Over Time")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout(); plt.savefig(IMG_DIR/"discovery_cumulative.png", dpi=150); plt.close()
    return df

def date_range(con):
    df = q(con, "SELECT MIN(date(endTime)) AS start, MAX(date(endTime)) AS end FROM listens")
    if df.empty: return "n/a"
    s,e = df.iloc[0]["start"], df.iloc[0]["end"]
    return f"{s} → {e}"

def guilty_pleasures(con):
    # many sessions but low total minutes: >=5 sessions AND total minutes < 12
    return q(con, """
        SELECT trackName, artistName,
               COUNT(*) AS play_sessions,
               ROUND(SUM(msPlayed)/60000.0, 1) AS minutes_total
        FROM listens
        GROUP BY trackName, artistName
        HAVING play_sessions >= 5 AND SUM(msPlayed) < 12*60000
        ORDER BY play_sessions DESC, minutes_total ASC
        LIMIT 20;
    """)

def what_if_drop_top(con):
    top = q(con, "SELECT artistName, SUM(msPlayed) AS ms FROM listens GROUP BY artistName ORDER BY ms DESC LIMIT 1;")
    if top.empty: return "n/a","n/a"
    top_artist = top.iloc[0]["artistName"]
    newtop = q(con, """
        WITH filtered AS (
            SELECT * FROM listens WHERE artistName != (SELECT artistName FROM (SELECT artistName, SUM(msPlayed) AS ms FROM listens GROUP BY artistName ORDER BY ms DESC LIMIT 1))
        )
        SELECT artistName, ROUND(SUM(msPlayed)/3600000.0,2) AS hours
        FROM filtered GROUP BY artistName ORDER BY hours DESC LIMIT 1;
    """)
    nt = newtop.iloc[0]["artistName"] if not newtop.empty else "n/a"
    return top_artist, nt

def optional_genres():
    p = CACHE_DIR / "artist_genres.csv"
    if not p.exists(): return False, None
    df = pd.read_csv(p)
    if "artistName" not in df or "genres" not in df: return False, None
    df["genres"] = df["genres"].fillna("")
    return True, df

def top_genres(con, genres_df):
    # map artist hours to genres (equal split among listed genres)
    hrs = q(con, "SELECT artistName, SUM(msPlayed)/3600000.0 AS hours FROM listens GROUP BY artistName")
    m = hrs.merge(genres_df, on="artistName", how="left")
    rows = []
    for _, r in m.iterrows():
        g = r.get("genres") if isinstance(r.get("genres"), str) else ""
        glist = [x.strip().title() for x in g.split("|") if x.strip()]
        if not glist:
            glist = ["Unknown"]
        w = r["hours"] / len(glist)
        for g in glist:
            rows.append({"genre": g, "hours": w})
    long = pd.DataFrame(rows)
    top = long.groupby("genre", as_index=False)["hours"].sum().sort_values("hours", ascending=False).head(15)
    return top

def main():
    if not DB.exists():
        raise SystemExit("Missing db/spotify.db. Copy your database into db/.")
    con = sqlite3.connect(DB)

    # Key numbers
    totals = (pd.read_sql_query("SELECT COUNT(*) AS plays, SUM(msPlayed)/3600000.0 AS hours FROM listens", con)).iloc[0]
    total_plays, total_hours = int(totals["plays"]), float(totals["hours"])
    uniq = (pd.read_sql_query("SELECT COUNT(DISTINCT artistName) AS artists, COUNT(DISTINCT trackName) AS tracks FROM listens", con)).iloc[0]
    unique_artists, unique_tracks = int(uniq["artists"]), int(uniq["tracks"])

    # Sections & charts
    topA = top_artists(con)
    topT = top_tracks(con)
    hhi, loyalty_label = compute_hhi(con)
    top_hours_list, peak_hours_label = plot_by_hour(con)
    top_weekdays_label = plot_by_weekday(con)
    plot_monthly(con)
    pct30, pct60 = skip_metrics(con)
    plays, dtracks, avg = repeat_metrics(con)
    replays = pd.read_sql_query("""
        SELECT trackName, artistName, COUNT(*) AS play_sessions, ROUND(SUM(msPlayed)/60000.0,1) AS minutes_listened
        FROM listens GROUP BY trackName, artistName
        HAVING play_sessions >= 3 ORDER BY play_sessions DESC, minutes_listened DESC LIMIT 20;""", con)
    binges_df = binges(con)
    disc = discovery(con)
    top_artist, new_top = what_if_drop_top(con)

    # Optional genres
    genre_available, gdf = optional_genres()
    if genre_available:
        topG = top_genres(con, gdf)
        top_genres_table = fmt_table(topG, 15)
    else:
        top_genres_table = ""

    # Render template
    template_path = ROOT / "src" / "report_template.md.j2"
    templ = Template(template_path.read_text(encoding="utf-8"))
    md = templ.render(
        date_range = date_range(con),
        total_hours = total_hours,
        total_plays = total_plays,
        unique_artists = unique_artists,
        unique_tracks = unique_tracks,
        top_artists_table = fmt_table(topA),
        top_tracks_table = fmt_table(topT),
        hhi = hhi,
        loyalty_label = loyalty_label,
        peak_hours = peak_hours_label,
        top_weekdays = top_weekdays_label,
        pct_lt_30s = pct30, pct_lt_60s = pct60,
        avg_plays_per_track = avg,
        top_replays_table = fmt_table(replays),
        binges_table = fmt_table(binges_df, 20),
        top_artist_name = top_artist, new_top_artist = new_top,
        genre_available = genre_available,
        top_genres_table = top_genres_table,
        guilty_table = fmt_table(guilty_pleasures(con), 20)
    )
    (OUT_DIR/"Spotify_Wrapped_Report.md").write_text(md, encoding="utf-8")
    print("Report written to outputs/Spotify_Wrapped_Report.md")

if __name__ == "__main__":
    main()
