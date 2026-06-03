# *Cinelog*

A personal movie journal that lives entirely on your computer. Log films you've watched with ratings and notes, keep a watchlist of films to see — no accounts, no cloud, no subscriptions.

---

## Screenshots

> Run locally and open `http://localhost:5001` to see it in action.

---

## Features

### Home
Poster grid of everything you've logged. Hover a card to reveal the title, year, and director. Filter between reviews and watchlist entries, sort by date or rating, and search across titles, directors, and cast.

### Reviews
Log watched films with a flexible rating and comment system.

- **Star ratings** — default overall rating (0–5 in 0.5 steps) plus optional custom-named ratings (e.g. *Cinematography*, *Soundtrack*, *Rewatch Value*)
- **Comments** — default review note plus optional custom comment sections, each with Markdown support and inline image attachments
- **Watch status** — mark entries as *Completed*, *In Progress*, or *Dropped*
- Custom rating and comment names are remembered and suggested as you type

### Watchlist
Queue films you want to see. Add freeform notes with custom comment modules. Search and filter your queue by title, director, or cast.

### Movie data
Search by title and select from live OMDb results — poster, cast, director, genre, and runtime fill in automatically.

---

## Tech Stack

| | |
|---|---|
| Backend | Python, Flask, SQLAlchemy |
| Database | SQLite (local file, no setup required) |
| Frontend | Vanilla JS, HTML, CSS |
| Movie data | [OMDb API](https://www.omdbapi.com/) — free tier, 1,000 req/day |

---

## Getting Started

### Prerequisites

- Python 3.10+
- A free OMDb API key → [omdbapi.com/apikey.aspx](https://www.omdbapi.com/apikey.aspx)

### Install

```bash
git clone https://github.com/dayeonisme/personal-cinelog.git
cd personal-cinelog
pip3 install -r requirements.txt
```

### Run

```bash
export OMDB_API_KEY="your_key_here"
python app.py
```

Open **http://localhost:5001**.

---

## Auto-start on Login (macOS)

Register Cinelog as a login item so it starts automatically with your Mac:

```bash
bash install_autostart.sh
```

To uninstall:

```bash
launchctl unload ~/Library/LaunchAgents/com.cinelog.app.plist
rm ~/Library/LaunchAgents/com.cinelog.app.plist
```

---

## Project Structure

```
cinelog/
├── app.py                   # Flask application & REST API
├── models.py                # SQLAlchemy models
├── database.py              # Database initialisation
├── requirements.txt
├── install_autostart.sh     # macOS launchd registration
├── static/
│   ├── css/style.css
│   ├── js/app.js
│   └── uploads/             # User-attached images (gitignored)
└── templates/
    └── index.html
```

---

## Data Model

```
Movie
└── Entry  (type: review | watchlist)
    ├── RatingModule   name · emoji · value (0–5)
    └── CommentModule  name · content (Markdown) · images[]
```

---

## Design

Cinematic dark-mode interface with a retro-futuristic terminal aesthetic — warm black and espresso backgrounds, bronze/gold accents, muted sage status indicators, and *Cormorant Garamond* italic for display typography.

---

*Personal use only. Not affiliated with IMDb or OMDb.*
