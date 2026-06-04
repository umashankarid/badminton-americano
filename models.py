"""Database setup and models using SQLite."""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "americano.db")


def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
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
            level TEXT NOT NULL,
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
    # First add missing columns
    for col in ['phone', 'email', 'card_type']:
        try:
            conn.execute(f"ALTER TABLE player ADD COLUMN {col} TEXT")
        except:
            pass

    # Remove CHECK constraint on level (to allow 'NA')
    try:
        info = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='player'").fetchone()
        if info and "CHECK" in info[0]:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS player_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    level TEXT NOT NULL,
                    phone TEXT,
                    email TEXT,
                    card_type TEXT,
                    points INTEGER NOT NULL DEFAULT 0
                );
                INSERT OR IGNORE INTO player_new (id, name, level, phone, email, card_type, points)
                    SELECT id, name, level, phone, email, card_type, points FROM player;
                DROP TABLE player;
                ALTER TABLE player_new RENAME TO player;
            """)
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
