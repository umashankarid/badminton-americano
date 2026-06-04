# Badminton Americano Tournament Organizer

A web application to organize badminton tournaments using the Americano format (2026 rules).

## Features

- **Player Management** — Add/edit players with levels (A, B, C)
- **Tournament Creation** — Configure name, level, max points, courts, and player selection
- **Americano Pairing** — Rotating partners ensuring everyone plays with everyone
- **Score-Balanced Matches** — Teams with similar points face each other for competitive games
- **Net Point System** — Points = your team's score minus opponent's score
- **Sit-Out Rotation** — Handles non-divisible-by-4 player counts fairly
- **Live Standings** — Updated after each match
- **Player Stats** — Match history, win/loss record per player
- **Multiple Tournaments** — Run several in parallel
- **Mobile-Friendly** — Designed for scoring at the court on a phone

## Quick Start

```bash
docker run -p 5000:5000 personalaccount/badminton-americano
```

Open http://localhost:5000

## Run Locally

```bash
pip install -r requirements.txt
python3 app.py
```

## Tech Stack

- Python / Flask
- SQLite
- Vanilla HTML/CSS/JS
