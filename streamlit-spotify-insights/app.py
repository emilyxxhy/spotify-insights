#!/usr/bin/env python3
import sqlite3, os, io, zipfile, pathlib
import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st

st.set_page_config(page_title="Spotify SQL Insights", layout="wide")

ROOT = pathlib.Path(__file__).resolve().parent

# Prefer app's db/spotify.db; if missing, automatically fall back to parent project db/
DEFAULT_DB = ROOT / "db" / "spotify.db"
PARENT_DB  = ROOT.parent / "db" / "spotify.db"
if (not DEFAULT_DB.exists()) and PARENT_DB.exists():
    DEFAULT_DB = PARENT_DB

@st.cache_resource(show_spinner=False)
def connect_sqlite(db_path: str | os.PathLike):
    # Open read-only and allow use across Streamlit threads
    uri = f"file:{pathlib.Path(db_path).as_posix()}?mode=ro&cache=shared"
    con = sqlite3.connect(uri, uri=True, check_same_thread=False)
    con.execute("PRAGMA busy_timeout=3000;")
    return con

def run_query(con, q: str, params=None) -> pd.DataFrame:
    return pd.read_sql_query(q, con, params=params)

# Sidebar: choose DB source
st.sidebar.title("Data Source")
db_choice = st.sidebar.radio("SQLite database", ["Use bundled db/spotify.db", "Upload .db file"])

con = None
if db_choice == "Use bundled db/spotify.db":
    if DEFAULT_DB.exists():
        con = connect_sqlite(DEFAULT_DB)
        st.sidebar.success(f"Connected: {DEFAULT_DB.name}")
    else:
        st.sidebar.error("db/spotify.db not found. Use upload option or copy your DB into /db.")
else:
    uploaded = st.sidebar.file_uploader("Upload a SQLite .db", type=["db","sqlite","sqlite3"])
    if uploaded is not None:
        tmp_path = ROOT / "uploaded.db"
        with open(tmp_path, "wb") as f:
            f.write(uploaded.getbuffer())
        con = connect_sqlite(tmp_path)
        st.sidebar.success("Uploaded DB connected.")

st.title("🎧 Spotify — SQL Insights (Streamlit)")

if con is None:
    st.info("Choose a database in the left sidebar to begin.")
    st.stop()

# Single tabs list (includes Gallery)
tabs = st.tabs(["Overview", "Artists", "Tracks", "Habits", "Discovery", "Gallery"])

# -------- Overview --------
with tabs[0]:
    colA, colB = st.columns([1,1])
    with colA:
        st.subheader("Top Artists (by hours)")
        df_top_artists = run_query(con, """
            SELECT artistName, ROUND(SUM(msPlayed)/3600000.0, 2) AS hours_listened, COUNT(*) AS plays
            FROM listens
            GROUP BY artistName
            ORDER BY hours_listened DESC, plays DESC
            LIMIT 15;
        """)
        st.dataframe(df_top_artists, use_container_width=True, hide_index=True)
        if not df_top_artists.empty:
            fig, ax = plt.subplots(figsize=(6,5))
            y = list(df_top_artists["artistName"])[::-1]
            x = list(df_top_artists["hours_listened"])[::-1]
            ax.barh(y, x); ax.set_xlabel("Hours"); ax.set_ylabel("Artist")
            ax.set_title("Top 15 Artists by Hours")
            st.pyplot(fig, use_container_width=True)

    with colB:
        st.subheader("Top Tracks (by hours)")
        df_top_tracks = run_query(con, """
            SELECT trackName, artistName, ROUND(SUM(msPlayed)/3600000.0, 2) AS hours_listened, COUNT(*) AS plays
            FROM listens
            GROUP BY trackName, artistName
            ORDER BY hours_listened DESC, plays DESC
            LIMIT 15;
        """)
        st.dataframe(df_top_tracks, use_container_width=True, hide_index=True)
        if not df_top_tracks.empty:
            fig, ax = plt.subplots(figsize=(6,5))
            names = [f"{t} — {a}" for t,a in zip(df_top_tracks["trackName"], df_top_tracks["artistName"])][::-1]
            vals  = list(df_top_tracks["hours_listened"])[::-1]
            ax.barh(names, vals); ax.set_xlabel("Hours"); ax.set_ylabel("Track — Artist")
            ax.set_title("Top 15 Tracks by Hours")
            st.pyplot(fig, use_container_width=True)

# -------- Artists --------
with tabs[1]:
    st.subheader("Artist Binges by Month (share %)")
    binge = run_query(con, """
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
    st.dataframe(binge, use_container_width=True, hide_index=True)
    st.caption("Artists who captured ≥30 minutes in a month, showing their share of that month's listening.")

    st.divider()
    st.subheader("Search an Artist")
    name = st.text_input("Artist name (exact match recommended)")
    if name:
        q = """
        SELECT date(endTime) AS date, ROUND(SUM(msPlayed)/3600000.0,2) AS hours
        FROM listens WHERE artistName = ? GROUP BY date ORDER BY date;
        """
        df = run_query(con, q, params=[name])
        st.dataframe(df, use_container_width=True, hide_index=True)
        if not df.empty:
            fig, ax = plt.subplots(figsize=(8,3))
            ax.plot(df["date"], df["hours"], marker="o")
            ax.set_title(f"Daily hours for {name}")
            ax.set_xlabel("Date"); ax.set_ylabel("Hours")
            plt.xticks(rotation=45, ha="right")
            st.pyplot(fig, use_container_width=True)

# -------- Tracks --------
with tabs[2]:
    left, right = st.columns([1,1])
    with left:
        st.subheader("Most Replayed Tracks (>=3 sessions)")
        top_rep = run_query(con, """
            SELECT trackName, artistName, COUNT(*) AS play_sessions, ROUND(SUM(msPlayed)/60000.0,1) AS minutes_listened
            FROM listens
            GROUP BY trackName, artistName
            HAVING play_sessions >= 3
            ORDER BY play_sessions DESC, minutes_listened DESC
            LIMIT 50;
        """)
        st.dataframe(top_rep, use_container_width=True, hide_index=True)

    with right:
        st.subheader("Skip Behavior (proxy)")
        skips = run_query(con, """
            SELECT
              COUNT(*) AS total_plays,
              SUM(CASE WHEN msPlayed < 30000 THEN 1 ELSE 0 END) AS plays_lt_30s,
              ROUND(100.0 * SUM(CASE WHEN msPlayed < 30000 THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_lt_30s,
              SUM(CASE WHEN msPlayed < 60000 THEN 1 ELSE 0 END) AS plays_lt_60s,
              ROUND(100.0 * SUM(CASE WHEN msPlayed < 60000 THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_lt_60s
            FROM listens;
        """)
        st.dataframe(skips, use_container_width=True, hide_index=True)

# -------- Habits --------
with tabs[3]:
    st.subheader("Listening by Hour of Day")
    by_hour = run_query(con, """
        SELECT CAST(strftime('%H', endTime) AS INTEGER) AS hour,
               ROUND(SUM(msPlayed)/3600000.0, 2) AS hours_listened
        FROM listens GROUP BY hour ORDER BY hour;
    """)
    fig, ax = plt.subplots(figsize=(8,3))
    if not by_hour.empty:
        ax.plot(by_hour["hour"], by_hour["hours_listened"], marker="o")
    ax.set_xlabel("Hour"); ax.set_ylabel("Hours")
    ax.set_title("By Hour")
    st.pyplot(fig, use_container_width=True)

    st.subheader("Listening by Weekday")
    by_wd = run_query(con, """
        SELECT CASE strftime('%w', endTime)
            WHEN '0' THEN 'Sun' WHEN '1' THEN 'Mon' WHEN '2' THEN 'Tue'
            WHEN '3' THEN 'Wed' WHEN '4' THEN 'Thu' WHEN '5' THEN 'Fri'
            WHEN '6' THEN 'Sat' END AS weekday,
            ROUND(SUM(msPlayed)/3600000.0, 2) AS hours_listened
        FROM listens GROUP BY strftime('%w', endTime) ORDER BY strftime('%w', endTime);
    """)
    fig2, ax2 = plt.subplots(figsize=(6,3))
    if not by_wd.empty:
        ax2.bar(by_wd["weekday"], by_wd["hours_listened"])
    ax2.set_xlabel("Weekday"); ax2.set_ylabel("Hours")
    ax2.set_title("By Weekday")
    st.pyplot(fig2, use_container_width=True)

    st.subheader("Monthly Trend")
    by_mon = run_query(con, """
        SELECT strftime('%Y-%m', endTime) AS month,
               ROUND(SUM(msPlayed)/3600000.0, 2) AS hours_listened,
               COUNT(DISTINCT artistName) AS unique_artists,
               COUNT(DISTINCT trackName) AS unique_tracks
        FROM listens GROUP BY month ORDER BY month;
    """)
    st.dataframe(by_mon, use_container_width=True, hide_index=True)
    if not by_mon.empty:
        fig3, ax3 = plt.subplots(figsize=(10,3))
        ax3.plot(by_mon["month"], by_mon["hours_listened"], marker="o")
        ax3.set_xlabel("Month"); ax3.set_ylabel("Hours")
        ax3.set_title("Monthly Listening Hours")
        plt.xticks(rotation=45, ha="right")
        st.pyplot(fig3, use_container_width=True)

# -------- Discovery --------
with tabs[4]:
    st.subheader("New Artists Over Time (Cumulative)")

    gran = st.radio("Granularity", ["Daily", "Weekly", "Monthly"], horizontal=True)

    disc = run_query(con, """
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

    if disc.empty:
        st.info("No data.")
    else:
        disc["date"] = pd.to_datetime(disc["date"])
        s = disc.set_index("date")["cumulative_artists"]

        # ---- optional resampling by granularity ----
        if gran == "Weekly":
            s = s.resample("W-SUN").last().dropna()
        elif gran == "Monthly":
            s = s.resample("MS").last().dropna()

        # ---- PUT YOUR DOWNSAMPLING HERE (before plotting) ----
        # keep at most ~600 points to draw
        max_pts = 600
        if len(s) > max_pts:
            step = max(1, len(s) // max_pts)
            s = s.iloc[::step]

        # ---- plot ----
        import matplotlib.dates as mdates
        fig, ax = plt.subplots(figsize=(10, 3))
        ax.plot(s.index, s.values, marker="o", ms=2, lw=1)
        ax.set_xlabel("Date"); ax.set_ylabel("Cumulative Artists")
        ax.set_title("Discovery Over Time")
        locator = mdates.AutoDateLocator(minticks=4, maxticks=8)
        ax.xaxis.set_major_locator(locator)
        ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
        fig.tight_layout()
        st.pyplot(fig, use_container_width=True)

# -------- Gallery --------
with tabs[5]:
    st.subheader("All Charts in outputs/")
    OUT = ROOT.parent / "outputs"
    imgs = sorted(OUT.glob("*.png")) + sorted((OUT / "report_images").glob("*.png"))
    if not imgs:
        st.info("No .png charts found in outputs/. Run your chart scripts first.")
    else:
        for p in imgs:
            st.markdown(f"**{p.relative_to(OUT)}**")
            st.image(str(p), use_container_width=True)
            st.divider()

        # Download everything as a zip (charts + CSV + report)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for p in OUT.glob("*.png"): z.write(p, p.name)
            for p in (OUT/"report_images").glob("*.png"): z.write(p, f"report_images/{p.name}")
            for p in OUT.glob("*.csv"): z.write(p, p.name)
            rp = OUT / "Spotify_Wrapped_Report.md"
            if rp.exists(): z.write(rp, rp.name)
        buf.seek(0)
        st.download_button("⬇️ Download all outputs (.zip)", buf, "spotify_outputs.zip", mime="application/zip")

st.caption("Tip: you can keep your DB in the app's /db folder or the parent project's /db — both work.")
