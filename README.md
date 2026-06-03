# *Cinelog*

> A personal movie journal — review films you've watched, track ones you want to see.

Runs locally on `localhost:5001`. No subscriptions, no cloud, no ads. Just your movies.

---

## Features

**Home** — poster grid of everything you've logged. Hover to reveal title, year, and director. Filter by type, sort by rating or date, and search across titles, directors, and cast.

**Reviews (평가)** — log films you've watched with a multi-module rating and comment system. Each entry supports a default star rating (0.5 steps) plus any number of custom-named ratings (e.g. *cinematography*, *OST*). Comments support Markdown and inline image attachments. Watch status tracks *완료 / 진행중 / 중단*.

**Watchlist (보고싶어요)** — queue films you want to see. Add freeform notes with custom comment modules. Movies are pulled from the OMDb API so posters, cast, and director fill in automatically.

---

## Stack

| Layer | Tech |
|---|---|
| Backend | Python · Flask · SQLAlchemy |
| Database | SQLite (local file) |
| Frontend | Vanilla JS · HTML · CSS |
| Movie data | [OMDb API](https://www.omdbapi.com/) (free tier) |

---

## Getting Started

### 1. Clone

```bash
git clone https://github.com/dayeonisme/personal-cinelog.git
cd personal-cinelog
```

### 2. Get a free OMDb API key

Register at [omdbapi.com/apikey.aspx](https://www.omdbapi.com/apikey.aspx) — free tier allows 1,000 requests/day.

### 3. Install dependencies

```bash
pip3 install -r requirements.txt
```

### 4. Run

```bash
export OMDB_API_KEY="your_key_here"
python app.py
```

Open **http://localhost:5001** in your browser.

---

## Auto-start on Login (macOS)

Run once to register Cinelog as a login item via `launchd`:

```bash
bash install_autostart.sh
```

Cinelog will start automatically every time you log in. To remove:

```bash
launchctl unload ~/Library/LaunchAgents/com.cinelog.app.plist
rm ~/Library/LaunchAgents/com.cinelog.app.plist
```

---

## Project Structure

```
cinelog/
├── app.py                  # Flask app + REST API
├── models.py               # SQLAlchemy models
├── database.py             # DB init
├── requirements.txt
├── install_autostart.sh    # macOS launchd setup
├── static/
│   ├── css/style.css
│   ├── js/app.js
│   └── uploads/            # Attached images (gitignored)
└── templates/
    └── index.html
```

---

## Data Model

```
Movie ──< Entry (review | watchlist)
              ├──< RatingModule   (name, emoji, value 0–5)
              └──< CommentModule  (name, content markdown, images[])
```

Custom rating and comment names are remembered across entries and appear as dropdown suggestions when adding new modules.

---

## UI

Cinematic dark-mode with a retro-futuristic terminal aesthetic. Warm black and espresso backgrounds, bronze/gold accents, muted sage green status indicators, and editorial serif typography (*Cormorant Garamond*) for display text.

---

*Personal use only. Not affiliated with IMDb or OMDb.*
