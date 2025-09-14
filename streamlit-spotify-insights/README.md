# Streamlit — Spotify SQL Insights

A Streamlit app that visualizes your Spotify listening analytics from **SQLite** (`db/spotify.db`).

## Quickstart
```bash
# 1) optional: create venv
python3 -m venv .venv
source .venv/bin/activate    # Windows: .\.venv\Scripts\Activate.ps1

# 2) install
pip install -r requirements.txt

# 3) put your database file
# copy your existing db/spotify.db into this project's db/ folder
# (or use the file uploader inside the app to load a DB on the fly)

# 4) run
streamlit run app.py
```

## Notes
- The app reads the same queries we used in your SQL project.
- If `db/spotify.db` is missing, use the **"Upload DB"** control to select your file.
