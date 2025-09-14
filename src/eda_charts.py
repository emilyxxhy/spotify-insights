#!/usr/bin/env python3
import sqlite3, pathlib
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

ROOT = pathlib.Path(__file__).resolve().parents[1]
DB = ROOT / "db" / "spotify.db"
OUT = ROOT / "outputs"
OUT.mkdir(exist_ok=True, parents=True)

def load_df(query: str) -> pd.DataFrame:
    con = sqlite3.connect(DB)
    df = pd.read_sql_query(query, con)
    con.close()
    return df

# ---------- existing charts ----------
def chart_top_artists():
    df = load_df("""
        SELECT artistName, SUM(msPlayed)/3600000.0 AS hours
        FROM listens GROUP BY artistName
        ORDER BY hours DESC LIMIT 15;
    """)
    if df.empty:
        return
    plt.figure(figsize=(10, 6))
    y = list(df["artistName"])[::-1]
    x = list(df["hours"])[::-1]
    plt.barh(y, x)
    plt.xlabel("Hours")
    plt.ylabel("Artist")
    plt.title("Top 15 Artists by Hours Listened")
    plt.tight_layout()
    plt.savefig(OUT / "chart_top_artists.png", dpi=150)
    plt.close()

def chart_by_hour():
    df = load_df("""
        SELECT CAST(strftime('%H', endTime) AS INTEGER) AS hour,
               SUM(msPlayed)/3600000.0 AS hours
        FROM listens GROUP BY hour ORDER BY hour;
    """)
    if df.empty:
        return
    plt.figure(figsize=(8, 5))
    plt.plot(df["hour"], df["hours"], marker="o")
    plt.xlabel("Hour (0-23)")
    plt.ylabel("Hours Listened")
    plt.title("Listening by Hour of Day")
    plt.xticks(range(0,24,1))
    plt.tight_layout()
    plt.savefig(OUT / "chart_by_hour.png", dpi=150)
    plt.close()

def chart_monthly_trend():
    df = load_df("""
        SELECT strftime('%Y-%m', endTime) AS month,
               SUM(msPlayed)/3600000.0 AS hours
        FROM listens GROUP BY month ORDER BY month;
    """)
    if df.empty:
        return
    plt.figure(figsize=(10, 5))
    plt.plot(df["month"], df["hours"], marker="o")
    plt.xlabel("Month")
    plt.ylabel("Hours Listened")
    plt.title("Monthly Listening Trend")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(OUT / "chart_monthly_trend.png", dpi=150)
    plt.close()

def chart_weekday():
    df = load_df("""
        SELECT CASE strftime('%w', endTime)
                WHEN '0' THEN 'Sun'
                WHEN '1' THEN 'Mon'
                WHEN '2' THEN 'Tue'
                WHEN '3' THEN 'Wed'
                WHEN '4' THEN 'Thu'
                WHEN '5' THEN 'Fri'
                WHEN '6' THEN 'Sat'
               END AS weekday,
               SUM(msPlayed)/3600000.0 AS hours
        FROM listens GROUP BY weekday;
    """)
    if df.empty:
        return
    order = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
    df["weekday"] = pd.Categorical(df["weekday"], categories=order, ordered=True)
    df = df.sort_values("weekday")
    plt.figure(figsize=(7,5))
    plt.bar(df["weekday"], df["hours"])
    plt.xlabel("Weekday")
    plt.ylabel("Hours Listened")
    plt.title("Listening by Weekday")
    plt.tight_layout()
    plt.savefig(OUT / "chart_weekday.png", dpi=150)
    plt.close()

# ---------- helpers ----------
def _ensure_daily(df: pd.DataFrame) -> pd.DataFrame:
    # df: columns ['date','hours']
    if df.empty:
        return df
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    full = pd.DataFrame({"date": pd.date_range(df["date"].min(), df["date"].max(), freq="D")})
    return full.merge(df, on="date", how="left").fillna({"hours": 0.0})

# ---------- new charts ----------
def chart_heatmap_hour_weekday():
    df = load_df("""
        SELECT CAST(strftime('%H', endTime) AS INTEGER) AS hour,
               strftime('%w', endTime) AS w,
               SUM(msPlayed)/3600000.0 AS hours
        FROM listens
        GROUP BY w, hour;
    """)
    if df.empty:
        return
    order = ['1','2','3','4','5','6','0']  # Mon..Sun
    mat = np.zeros((7, 24), dtype=float)
    for i, w in enumerate(order):
        sub = df[df["w"] == w].set_index("hour")["hours"].to_dict()
        for h in range(24):
            mat[i, h] = float(sub.get(h, 0.0))
    fig, ax = plt.subplots(figsize=(10, 4))
    im = ax.imshow(mat, aspect="auto")
    ax.set_yticks(range(7))
    ax.set_yticklabels(["Mon","Tue","Wed","Thu","Fri","Sat","Sun"])
    ax.set_xticks(range(0,24,2))
    ax.set_xlabel("Hour of Day")
    ax.set_title("Listening Heatmap (Weekday × Hour)")
    fig.colorbar(im, ax=ax, label="Hours")
    fig.tight_layout()
    fig.savefig(OUT / "chart_heatmap_hour_weekday.png", dpi=150)
    plt.close(fig)

def chart_rolling_30d():
    df = load_df("""
        SELECT date(endTime) AS date, SUM(msPlayed)/3600000.0 AS hours
        FROM listens GROUP BY date ORDER BY date;
    """)
    if df.empty:
        return
    df = _ensure_daily(df)
    df["roll30"] = df["hours"].rolling(30, min_periods=1).sum()
    fig, ax = plt.subplots(figsize=(10, 3))
    ax.plot(df["date"], df["roll30"])
    ax.set_title("Rolling 30-Day Listening Hours")
    ax.set_xlabel("Date"); ax.set_ylabel("Hours (30d sum)")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(OUT / "chart_rolling_30d.png", dpi=150)
    plt.close(fig)

def chart_session_duration_hist():
    df = load_df("SELECT msPlayed FROM listens;")
    if df.empty:
        return
    mins = df["msPlayed"] / 60000.0
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.hist(mins, bins=50)
    ax.set_xlabel("Session Minutes (per play)")
    ax.set_ylabel("Count")
    ax.set_title("Distribution of Session Durations")
    fig.tight_layout()
    fig.savefig(OUT / "chart_session_duration_hist.png", dpi=150)
    plt.close(fig)

def chart_cumulative_hours():
    df = load_df("""
        SELECT date(endTime) AS date, SUM(msPlayed)/3600000.0 AS hours
        FROM listens GROUP BY date ORDER BY date;
    """)
    if df.empty:
        return
    df = _ensure_daily(df)
    df["cum"] = df["hours"].cumsum()
    fig, ax = plt.subplots(figsize=(10, 3))
    ax.plot(df["date"], df["cum"])
    ax.set_xlabel("Date"); ax.set_ylabel("Cumulative Hours")
    ax.set_title("Cumulative Listening Hours")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(OUT / "chart_cumulative_hours.png", dpi=150)
    plt.close(fig)

def chart_top5_artists_monthly_stacked():
    # pick top 5 artists overall by hours
    top5 = load_df("""
        SELECT artistName, SUM(msPlayed) AS ms
        FROM listens GROUP BY artistName
        ORDER BY ms DESC LIMIT 5;
    """)
    if top5.empty:
        return
    artists = top5["artistName"].tolist()
    df = load_df("""
        SELECT strftime('%Y-%m', endTime) AS month, artistName, SUM(msPlayed)/3600000.0 AS hours
        FROM listens GROUP BY month, artistName ORDER BY month;
    """)
    df = df[df["artistName"].isin(artists)]
    if df.empty:
        return
    months = sorted(df["month"].unique().tolist())
    M = len(months)
    mat = np.zeros((len(artists), M))
    for i, a in enumerate(artists):
        sub = df[df["artistName"] == a].set_index("month")["hours"].to_dict()
        mat[i] = [float(sub.get(m, 0.0)) for m in months]
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.stackplot(range(M), *mat, labels=artists)
    ax.set_xticks(range(M))
    ax.set_xticklabels(months, rotation=45, ha="right")
    ax.set_ylabel("Hours")
    ax.set_title("Top 5 Artists — Monthly Hours (Stacked)")
    ax.legend(loc="upper left", fontsize=8, ncol=2)
    fig.tight_layout()
    fig.savefig(OUT / "chart_top5_artists_monthly_stacked.png", dpi=150)
    plt.close(fig)

def main():
    # existing
    chart_top_artists()
    chart_by_hour()
    chart_monthly_trend()
    chart_weekday()
    # new
    chart_heatmap_hour_weekday()
    chart_rolling_30d()
    chart_session_duration_hist()
    chart_cumulative_hours()
    chart_top5_artists_monthly_stacked()
    print("Charts saved to outputs/.")

if __name__ == "__main__":
    main()
