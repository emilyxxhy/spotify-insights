#!/usr/bin/env python3
import sqlite3, pathlib, pandas as pd
ROOT = pathlib.Path(__file__).resolve().parents[1]
DB = ROOT / "db" / "spotify.db"
SQL_DIR = ROOT / "sql"
OUT = ROOT / "outputs"
OUT.mkdir(exist_ok=True, parents=True)
def run_sql(name: str):
    sql_path = SQL_DIR / name
    with open(sql_path, "r", encoding="utf-8") as f:
        q = f.read()
    con = sqlite3.connect(DB)
    df = pd.read_sql_query(q, con)
    con.close()
    df.to_csv(OUT / f"{name.replace('.sql','.csv')}", index=False)
    return df
def main():
    sections = ["top_artists.sql","top_tracks.sql","by_hour.sql","by_weekday.sql","by_month.sql","artist_binges.sql","skips.sql","repeats.sql","top_replays.sql","discovery.sql"]
    results = {name: run_sql(name) for name in sections}
    # insights
    ta = results["top_artists.sql"].head(5)
    tt = results["top_tracks.sql"].head(5)
    skips = results["skips.sql"].iloc[0]
    repeats = results["repeats.sql"].iloc[0]
    by_hour = results["by_hour.sql"].sort_values("hours_listened", ascending=False).head(3)
    by_weekday = results["by_weekday.sql"].sort_values("hours_listened", ascending=False).head(3)
    lines = ["# Spotify SQL Insights\n","## Highlights\n"]
    if not ta.empty:
        top_artist = ta.iloc[0]
        lines.append(f"- **Top artist:** {top_artist['artistName']} ({top_artist['hours_listened']} hours).")
    if not tt.empty:
        top_track = tt.iloc[0]
        lines.append(f"- **Top track:** \"{top_track['trackName']}\" — {top_track['artistName']} ({top_track['hours_listened']} hours).")
    lines.append(f"- **Skipping proxy (<30s):** {skips['pct_lt_30s']}% of plays; <60s: {skips['pct_lt_60s']}%.")
    lines.append(f"- **Repeat rate:** {repeats['avg_plays_per_track']} plays per distinct track.")
    lines.append("- **Peak hours:** " + ", ".join(str(int(r['hour'])) for _, r in by_hour.iterrows()) + "h.")
    lines.append("- **Top weekdays:** " + ", ".join(r['weekday'] for _, r in by_weekday.iterrows()) + ".")
    (OUT / "insights.md").write_text("\n".join(lines), encoding="utf-8")
    print("Wrote CSVs and insights.md to outputs/")
if __name__ == "__main__":
    main()
