"""Database setup and models using SQLite."""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "americano.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS card_type (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        );

        INSERT OR IGNORE INTO card_type (name) VALUES ('Max Card');
        INSERT OR IGNORE INTO card_type (name) VALUES ('Season Card');
        INSERT OR IGNORE INTO card_type (name) VALUES ('Club Junior');

        CREATE TABLE IF NOT EXISTS player (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            level TEXT NOT NULL CHECK(level IN ('A', 'B', 'C')),
            phone TEXT,
            email TEXT,
            card_type TEXT,
            points INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS season (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            start_date TEXT,
            end_date TEXT,
            registration_deadline TEXT,
            status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'finished'))
        );

        CREATE TABLE IF NOT EXISTS season_player (
            season_id INTEGER NOT NULL,
            player_id INTEGER NOT NULL,
            PRIMARY KEY (season_id, player_id),
            FOREIGN KEY (season_id) REFERENCES season(id),
            FOREIGN KEY (player_id) REFERENCES player(id)
        );

        CREATE TABLE IF NOT EXISTS tournament (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            level TEXT NOT NULL CHECK(level IN ('A', 'B', 'C', 'No-level')),
            max_points INTEGER NOT NULL DEFAULT 15,
            courts INTEGER NOT NULL DEFAULT 1,
            date TEXT,
            season_id INTEGER,
            status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'finished')),
            current_round INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (season_id) REFERENCES season(id)
        );

        CREATE TABLE IF NOT EXISTS tournament_player (
            tournament_id INTEGER NOT NULL,
            player_id INTEGER NOT NULL,
            points INTEGER NOT NULL DEFAULT 0,
            sit_outs INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (tournament_id, player_id),
            FOREIGN KEY (tournament_id) REFERENCES tournament(id),
            FOREIGN KEY (player_id) REFERENCES player(id)
        );

        CREATE TABLE IF NOT EXISTS match (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tournament_id INTEGER NOT NULL,
            round_num INTEGER NOT NULL,
            court_num INTEGER NOT NULL,
            player_a1 INTEGER NOT NULL,
            player_a2 INTEGER NOT NULL,
            player_b1 INTEGER NOT NULL,
            player_b2 INTEGER NOT NULL,
            score_a INTEGER,
            score_b INTEGER,
            played INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (tournament_id) REFERENCES tournament(id),
            FOREIGN KEY (player_a1) REFERENCES player(id),
            FOREIGN KEY (player_a2) REFERENCES player(id),
            FOREIGN KEY (player_b1) REFERENCES player(id),
            FOREIGN KEY (player_b2) REFERENCES player(id)
        );
    """)
    conn.commit()

    # Migrations for existing databases
    try:
        conn.execute("ALTER TABLE player ADD COLUMN phone TEXT")
    except:
        pass
    try:
        conn.execute("ALTER TABLE player ADD COLUMN email TEXT")
    except:
        pass
    try:
        conn.execute("ALTER TABLE player ADD COLUMN card_type TEXT")
    except:
        pass
    try:
        conn.execute("ALTER TABLE tournament ADD COLUMN date TEXT")
    except:
        pass
    try:
        conn.execute("ALTER TABLE tournament ADD COLUMN season_id INTEGER")
    except:
        pass
    try:
        conn.execute("ALTER TABLE season ADD COLUMN start_date TEXT")
    except:
        pass
    try:
        conn.execute("ALTER TABLE season ADD COLUMN end_date TEXT")
    except:
        pass
    try:
        conn.execute("ALTER TABLE season ADD COLUMN registration_deadline TEXT")
    except:
        pass
    conn.commit()
    conn.close()
