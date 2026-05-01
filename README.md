# Feinbermetrics

MLB schedule win-probability analyzer. Pulls all 30 teams' season schedules from FanGraphs, stores them in a local SQLite database, and surfaces a Streamlit dashboard with a week picker and sweep-probability leaderboard.

---

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Set your password

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

Open `.streamlit/secrets.toml` and change `app_password` to whatever you want.  
This file is in `.gitignore` — it will never be committed.

### 3. Fetch schedule data

```bash
python fetch_schedules.py
```

This loops through all 30 MLB team IDs, hits the FanGraphs schedule API, and writes every game into `schedules.db`. Re-run at any point during the season to refresh results.

> **Note:** On the first run the script prints a sample raw API record so you can verify the field mapping is correct. If any field names differ from what FanGraphs returns, adjust the `normalize_game` function in `fetch_schedules.py`.

### 4. Run the app

```bash
streamlit run app.py
```

The app opens at `http://localhost:8501`. Sign in with the password you set.

---

## Features

| Feature | Description |
|---|---|
| Week picker | Select any Mon–Sun week from a dropdown |
| Custom date range | Override with any start/end date |
| Sweep probability leaderboard | Ranked by P(win every game in window) |
| Game breakdown | Per-team game list with win prob, result, score |
| CSV export | Download leaderboard or per-team data |

**Sweep probability** = product of win probabilities across all a team's games in the selected window. A team playing 3 games at 65% / 70% / 72% has a ~33% sweep probability.

---

## Sharing

### Option A — Share the repo (local run)

Your friend clones the repo and runs the same four steps above.

### Option B — Streamlit Community Cloud (recommended for a live URL)

1. Push this repo to GitHub (it's already set up for `JTFeinberg/feinbermetrics`)
2. Go to [share.streamlit.io](https://share.streamlit.io) and connect the repo
3. In the Streamlit Cloud dashboard, add your secret under **Settings → Secrets**:
   ```toml
   app_password = "your_password"
   ```
4. Share the public URL — no install required for your friend

---

## Project structure

```
feinbermetrics/
├── fetch_schedules.py        # Data fetcher — hits FanGraphs, writes schedules.db
├── app.py                    # Streamlit dashboard
├── requirements.txt
├── .gitignore
├── .streamlit/
│   ├── secrets.toml.example  # Template — copy to secrets.toml and set password
│   └── secrets.toml          # ← YOU CREATE THIS (gitignored)
└── schedules.db              # ← AUTO-GENERATED (gitignored)
```
