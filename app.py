"""Flask application for Badminton Americano tournament."""
import os
from functools import wraps
from flask import Flask, request, jsonify, render_template, send_file, session
from models import get_db, init_db, DB_PATH
from pairing import generate_round_pairings, get_used_pairs, get_tournament_points, get_sit_out_counts

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "komet-badminton-2026")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "komet2026")


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin"):
            return jsonify({"error": "Admin login required"}), 401
        return f(*args, **kwargs)
    return decorated


@app.before_request
def before_request():
    init_db()


# --- Pages ---
@app.route("/")
def index():
    return render_template("index.html")


# --- Auth API ---
@app.route("/api/admin/login", methods=["POST"])
def admin_login():
    data = request.json
    if data.get("password") == ADMIN_PASSWORD:
        session["admin"] = True
        return jsonify({"ok": True})
    return jsonify({"error": "Wrong password"}), 401


@app.route("/api/admin/logout", methods=["POST"])
def admin_logout():
    session.pop("admin", None)
    return jsonify({"ok": True})


@app.route("/api/admin/status")
def admin_status():
    return jsonify({"admin": session.get("admin", False)})


@app.route("/tournament/<slug>")
def tournament_view(slug):
    return render_template("tournament.html", tournament_slug=slug)


@app.route("/season/<int:sid>")
def season_view(sid):
    return render_template("season.html", season_id=sid)


@app.route("/player/<int:pid>")
def player_view(pid):
    return render_template("player.html", player_id=pid)


# --- Player API ---
@app.route("/api/players", methods=["GET"])
def list_players():
    level = request.args.get("level")
    db = get_db()
    if level and level != "No-level":
        rows = db.execute("SELECT * FROM player WHERE level = ? ORDER BY points DESC", (level,)).fetchall()
    else:
        rows = db.execute("SELECT * FROM player ORDER BY points DESC").fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/players", methods=["POST"])
def add_player():
    data = request.json
    db = get_db()
    existing = db.execute("SELECT id FROM player WHERE name = ?", (data["name"],)).fetchone()
    if existing:
        db.close()
        return jsonify({"error": "Player already exists"}), 400
    try:
        db.execute("INSERT INTO player (name, level) VALUES (?, ?)", (data["name"], data["level"]))
        db.commit()
    except Exception as e:
        db.close()
        return jsonify({"error": str(e)}), 400
    db.close()
    return jsonify({"ok": True}), 201


@app.route("/api/players/<int:pid>", methods=["PUT"])
def edit_player(pid):
    data = request.json
    db = get_db()
    db.execute("UPDATE player SET name = ?, level = ? WHERE id = ?", (data["name"], data["level"], pid))
    db.commit()
    db.close()
    return jsonify({"ok": True})


@app.route("/api/players/<int:pid>", methods=["DELETE"])
@admin_required
def delete_player(pid):
    db = get_db()
    # Check if player is in any active tournament
    active = db.execute(
        "SELECT t.name FROM tournament_player tp JOIN tournament t ON tp.tournament_id = t.id WHERE tp.player_id = ? AND t.status = 'active' AND t.current_round > 0",
        (pid,)
    ).fetchone()
    if active:
        db.close()
        return jsonify({"error": f"Cannot delete: player is in active tournament '{active['name']}'"}), 400
    db.execute("DELETE FROM tournament_player WHERE player_id = ?", (pid,))
    db.execute("DELETE FROM player WHERE id = ?", (pid,))
    db.commit()
    db.close()
    return jsonify({"ok": True})


@app.route("/api/players/<int:pid>/stats", methods=["GET"])
def player_stats(pid):
    db = get_db()
    player = dict(db.execute("SELECT * FROM player WHERE id = ?", (pid,)).fetchone())
    matches = db.execute(
        """SELECT m.*, t.name as tournament_name,
           pa1.name as a1_name, pa2.name as a2_name, pb1.name as b1_name, pb2.name as b2_name
           FROM match m
           JOIN tournament t ON m.tournament_id = t.id
           JOIN player pa1 ON m.player_a1 = pa1.id
           JOIN player pa2 ON m.player_a2 = pa2.id
           JOIN player pb1 ON m.player_b1 = pb1.id
           JOIN player pb2 ON m.player_b2 = pb2.id
           WHERE (m.player_a1 = ? OR m.player_a2 = ? OR m.player_b1 = ? OR m.player_b2 = ?) AND m.played = 1
           ORDER BY m.id DESC""", (pid, pid, pid, pid)
    ).fetchall()
    match_list = []
    wins = 0
    for m in matches:
        on_team_a = pid in (m["player_a1"], m["player_a2"])
        won = (on_team_a and m["score_a"] > m["score_b"]) or (not on_team_a and m["score_b"] > m["score_a"])
        if won:
            wins += 1
        match_list.append({**dict(m), "won": won, "on_team_a": on_team_a})
    player["matches"] = match_list
    player["total_matches"] = len(match_list)
    player["wins"] = wins
    player["losses"] = len(match_list) - wins
    db.close()
    return jsonify(player)


# --- Tournament API ---
def slugify(name):
    return name.lower().replace(" ", "-")


# --- Season API ---
@app.route("/api/seasons", methods=["GET"])
def list_seasons():
    db = get_db()
    rows = db.execute("SELECT * FROM season ORDER BY id DESC").fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/seasons", methods=["POST"])
@admin_required
def create_season():
    data = request.json
    db = get_db()
    existing = db.execute("SELECT id FROM season WHERE name = ?", (data["name"],)).fetchone()
    if existing:
        db.close()
        return jsonify({"error": "Season with this name already exists"}), 400
    cur = db.execute("INSERT INTO season (name, description, start_date, end_date, registration_deadline) VALUES (?, ?, ?, ?, ?)",
                     (data["name"], data.get("description", ""), data.get("start_date"), data.get("end_date"), data.get("registration_deadline")))
    db.commit()
    db.close()
    return jsonify({"id": cur.lastrowid}), 201


@app.route("/api/seasons/<int:sid>", methods=["GET"])
def get_season(sid):
    db = get_db()
    s = db.execute("SELECT * FROM season WHERE id = ?", (sid,)).fetchone()
    if not s:
        db.close()
        return jsonify({"error": "Season not found"}), 404
    s = dict(s)
    players = db.execute(
        "SELECT p.* FROM season_player sp JOIN player p ON sp.player_id = p.id WHERE sp.season_id = ? ORDER BY p.name",
        (sid,)
    ).fetchall()
    s["players"] = [dict(r) for r in players]
    tournaments = db.execute(
        "SELECT * FROM tournament WHERE season_id = ? ORDER BY date, id", (sid,)
    ).fetchall()
    s["tournaments"] = [dict(r) for r in tournaments]
    db.close()
    return jsonify(s)


@app.route("/api/seasons/<int:sid>", methods=["PUT"])
@admin_required
def edit_season(sid):
    data = request.json
    db = get_db()
    existing = db.execute("SELECT id FROM season WHERE name = ? AND id != ?", (data["name"], sid)).fetchone()
    if existing:
        db.close()
        return jsonify({"error": "Season with this name already exists"}), 400
    db.execute("UPDATE season SET name=?, description=?, start_date=?, end_date=?, registration_deadline=? WHERE id=?",
               (data["name"], data.get("description", ""), data.get("start_date"), data.get("end_date"), data.get("registration_deadline"), sid))
    db.commit()
    db.close()
    return jsonify({"ok": True})


@app.route("/api/seasons/<int:sid>", methods=["DELETE"])
@admin_required
def delete_season(sid):
    db = get_db()
    db.execute("DELETE FROM season_player WHERE season_id = ?", (sid,))
    db.execute("UPDATE tournament SET season_id = NULL WHERE season_id = ?", (sid,))
    db.execute("DELETE FROM season WHERE id = ?", (sid,))
    db.commit()
    db.close()
    return jsonify({"ok": True})


@app.route("/api/seasons/<int:sid>/join", methods=["POST"])
def join_season(sid):
    data = request.json
    pid = data["player_id"]
    db = get_db()
    season = db.execute("SELECT * FROM season WHERE id = ?", (sid,)).fetchone()
    if season["registration_deadline"]:
        from datetime import date
        if date.today().isoformat() > season["registration_deadline"]:
            db.close()
            return jsonify({"error": "Registration deadline has passed"}), 400
    existing = db.execute("SELECT 1 FROM season_player WHERE season_id = ? AND player_id = ?", (sid, pid)).fetchone()
    if existing:
        db.close()
        return jsonify({"error": "Already registered for this season"}), 400
    db.execute("INSERT INTO season_player (season_id, player_id) VALUES (?, ?)", (sid, pid))
    db.commit()
    db.close()
    return jsonify({"ok": True})


@app.route("/api/seasons/<int:sid>/leave", methods=["POST"])
def leave_season(sid):
    data = request.json
    pid = data["player_id"]
    db = get_db()
    db.execute("DELETE FROM season_player WHERE season_id = ? AND player_id = ?", (sid, pid))
    db.commit()
    db.close()
    return jsonify({"ok": True})


@app.route("/api/tournaments/by-slug/<slug>", methods=["GET"])
def get_tournament_by_slug(slug):
    db = get_db()
    rows = db.execute("SELECT * FROM tournament").fetchall()
    t = None
    for r in rows:
        if slugify(r["name"]) == slug:
            t = dict(r)
            break
    if not t:
        db.close()
        return jsonify({"error": "Tournament not found"}), 404
    players = db.execute(
        """SELECT p.id, p.name, p.level, tp.points as tournament_points, tp.sit_outs
           FROM tournament_player tp JOIN player p ON tp.player_id = p.id
           WHERE tp.tournament_id = ? ORDER BY tp.points DESC""", (t["id"],)
    ).fetchall()
    t["players"] = [dict(r) for r in players]
    matches = db.execute(
        """SELECT m.*, pa1.name as a1_name, pa2.name as a2_name, pb1.name as b1_name, pb2.name as b2_name
           FROM match m
           JOIN player pa1 ON m.player_a1 = pa1.id
           JOIN player pa2 ON m.player_a2 = pa2.id
           JOIN player pb1 ON m.player_b1 = pb1.id
           JOIN player pb2 ON m.player_b2 = pb2.id
           WHERE m.tournament_id = ? ORDER BY m.round_num, m.court_num""", (t["id"],)
    ).fetchall()
    t["matches"] = [dict(r) for r in matches]
    db.close()
    return jsonify(t)


@app.route("/api/tournaments", methods=["GET"])
def list_tournaments():
    db = get_db()
    rows = db.execute("SELECT * FROM tournament ORDER BY id DESC").fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/tournaments", methods=["POST"])
@admin_required
def create_tournament():
    data = request.json
    db = get_db()
    existing = db.execute("SELECT id FROM tournament WHERE name = ?", (data["name"],)).fetchone()
    if existing:
        db.close()
        return jsonify({"error": "Tournament with this name already exists"}), 400
    cur = db.execute(
        "INSERT INTO tournament (name, level, max_points, courts, date, season_id) VALUES (?, ?, ?, ?, ?, ?)",
        (data["name"], data["level"], data["max_points"], data["courts"], data.get("date"), data.get("season_id"))
    )
    tid = cur.lastrowid
    for pid in data.get("player_ids", []):
        db.execute("INSERT INTO tournament_player (tournament_id, player_id) VALUES (?, ?)", (tid, pid))
    db.commit()
    db.close()
    return jsonify({"id": tid}), 201


@app.route("/api/tournaments/<int:tid>", methods=["PUT"])
@admin_required
def edit_tournament(tid):
    data = request.json
    db = get_db()
    t = db.execute("SELECT * FROM tournament WHERE id = ?", (tid,)).fetchone()
    if t["current_round"] > 0:
        db.close()
        return jsonify({"error": "Cannot edit a tournament that has already started"}), 400
    existing = db.execute("SELECT id FROM tournament WHERE name = ? AND id != ?", (data["name"], tid)).fetchone()
    if existing:
        db.close()
        return jsonify({"error": "Tournament with this name already exists"}), 400
    db.execute("UPDATE tournament SET name=?, level=?, max_points=?, courts=?, date=? WHERE id=?",
               (data["name"], data["level"], data["max_points"], data["courts"], data.get("date"), tid))
    db.execute("DELETE FROM tournament_player WHERE tournament_id = ?", (tid,))
    for pid in data["player_ids"]:
        db.execute("INSERT INTO tournament_player (tournament_id, player_id) VALUES (?, ?)", (tid, pid))
    db.commit()
    db.close()
    return jsonify({"ok": True})


@app.route("/api/tournaments/<int:tid>/join", methods=["POST"])
def join_tournament(tid):
    data = request.json
    pid = data["player_id"]
    db = get_db()
    t = db.execute("SELECT * FROM tournament WHERE id = ?", (tid,)).fetchone()
    if t["current_round"] > 0:
        db.close()
        return jsonify({"error": "Tournament already started"}), 400
    existing = db.execute("SELECT 1 FROM tournament_player WHERE tournament_id = ? AND player_id = ?", (tid, pid)).fetchone()
    if existing:
        db.close()
        return jsonify({"error": "Already in this tournament"}), 400
    db.execute("INSERT INTO tournament_player (tournament_id, player_id) VALUES (?, ?)", (tid, pid))
    db.commit()
    db.close()
    return jsonify({"ok": True})


@app.route("/api/tournaments/<int:tid>/leave", methods=["POST"])
def leave_tournament(tid):
    data = request.json
    pid = data["player_id"]
    db = get_db()
    t = db.execute("SELECT * FROM tournament WHERE id = ?", (tid,)).fetchone()
    if t["current_round"] > 0:
        db.close()
        return jsonify({"error": "Tournament already started"}), 400
    db.execute("DELETE FROM tournament_player WHERE tournament_id = ? AND player_id = ?", (tid, pid))
    db.commit()
    db.close()
    return jsonify({"ok": True})


@app.route("/api/tournaments/<int:tid>", methods=["DELETE"])
@admin_required
def delete_tournament(tid):
    db = get_db()
    db.execute("DELETE FROM match WHERE tournament_id = ?", (tid,))
    db.execute("DELETE FROM tournament_player WHERE tournament_id = ?", (tid,))
    db.execute("DELETE FROM tournament WHERE id = ?", (tid,))
    db.commit()
    db.close()
    return jsonify({"ok": True})


@app.route("/api/tournaments/<int:tid>", methods=["GET"])
def get_tournament(tid):
    db = get_db()
    t = dict(db.execute("SELECT * FROM tournament WHERE id = ?", (tid,)).fetchone())
    players = db.execute(
        """SELECT p.id, p.name, p.level, tp.points as tournament_points, tp.sit_outs
           FROM tournament_player tp JOIN player p ON tp.player_id = p.id
           WHERE tp.tournament_id = ? ORDER BY tp.points DESC""", (tid,)
    ).fetchall()
    t["players"] = [dict(r) for r in players]
    matches = db.execute(
        """SELECT m.*, pa1.name as a1_name, pa2.name as a2_name, pb1.name as b1_name, pb2.name as b2_name
           FROM match m
           JOIN player pa1 ON m.player_a1 = pa1.id
           JOIN player pa2 ON m.player_a2 = pa2.id
           JOIN player pb1 ON m.player_b1 = pb1.id
           JOIN player pb2 ON m.player_b2 = pb2.id
           WHERE m.tournament_id = ? ORDER BY m.round_num, m.court_num""", (tid,)
    ).fetchall()
    t["matches"] = [dict(r) for r in matches]
    db.close()
    return jsonify(t)


@app.route("/api/tournaments/<int:tid>/next-round", methods=["POST"])
@admin_required
def generate_next_round(tid):
    db = get_db()
    t = db.execute("SELECT * FROM tournament WHERE id = ?", (tid,)).fetchone()
    if t["status"] == "finished":
        db.close()
        return jsonify({"error": "Tournament is finished"}), 400

    player_rows = db.execute("SELECT player_id FROM tournament_player WHERE tournament_id = ?", (tid,)).fetchall()
    player_ids = [r["player_id"] for r in player_rows]

    if len(player_ids) < 4:
        db.close()
        return jsonify({"error": "Need at least 4 players to start"}), 400

    used_pairs = get_used_pairs(db, tid)
    player_points = get_tournament_points(db, tid)
    sit_out_counts = get_sit_out_counts(db, tid)
    round_num = t["current_round"] + 1

    result = generate_round_pairings(player_ids, used_pairs, t["courts"], player_points, sit_out_counts)
    matches, sitting_out = result

    if not matches:
        db.execute("UPDATE tournament SET status = 'finished' WHERE id = ?", (tid,))
        db.commit()
        db.close()
        return jsonify({"finished": True, "message": "All partnerships played. Tournament complete!"})

    for court, (a1, a2, b1, b2) in enumerate(matches, 1):
        db.execute(
            "INSERT INTO match (tournament_id, round_num, court_num, player_a1, player_a2, player_b1, player_b2) VALUES (?,?,?,?,?,?,?)",
            (tid, round_num, court, a1, a2, b1, b2)
        )

    # Update sit-out counts
    for pid in sitting_out:
        db.execute("UPDATE tournament_player SET sit_outs = sit_outs + 1 WHERE tournament_id = ? AND player_id = ?",
                   (tid, pid))

    db.execute("UPDATE tournament SET current_round = ? WHERE id = ?", (round_num, tid))
    db.commit()

    # Get names of sitting out players
    sit_out_names = []
    if sitting_out:
        for pid in sitting_out:
            row = db.execute("SELECT name FROM player WHERE id = ?", (pid,)).fetchone()
            sit_out_names.append(row["name"])

    db.close()
    return jsonify({"round": round_num, "sitting_out": sit_out_names})


@app.route("/api/matches/<int:mid>/score", methods=["POST"])
@admin_required
def record_score(mid):
    data = request.json
    score_a, score_b = data["score_a"], data["score_b"]
    db = get_db()
    match = db.execute("SELECT * FROM match WHERE id = ?", (mid,)).fetchone()
    t = db.execute("SELECT max_points FROM tournament WHERE id = ?", (match["tournament_id"],)).fetchone()
    max_pts = t["max_points"]

    if max(score_a, score_b) != max_pts:
        db.close()
        return jsonify({"error": f"Winning score must be {max_pts}"}), 400
    if min(score_a, score_b) < 0 or min(score_a, score_b) >= max_pts:
        db.close()
        return jsonify({"error": f"Losing score must be 0-{max_pts - 1}"}), 400

    net_a = score_a - score_b
    net_b = score_b - score_a

    # If already played, undo old score first
    if match["played"]:
        old_net_a = match["score_a"] - match["score_b"]
        old_net_b = match["score_b"] - match["score_a"]
        for pid in (match["player_a1"], match["player_a2"]):
            db.execute("UPDATE tournament_player SET points = points - ? WHERE tournament_id = ? AND player_id = ?",
                       (old_net_a, match["tournament_id"], pid))
            db.execute("UPDATE player SET points = points - ? WHERE id = ?", (old_net_a, pid))
        for pid in (match["player_b1"], match["player_b2"]):
            db.execute("UPDATE tournament_player SET points = points - ? WHERE tournament_id = ? AND player_id = ?",
                       (old_net_b, match["tournament_id"], pid))
            db.execute("UPDATE player SET points = points - ? WHERE id = ?", (old_net_b, pid))

    db.execute("UPDATE match SET score_a = ?, score_b = ?, played = 1 WHERE id = ?", (score_a, score_b, mid))

    for pid in (match["player_a1"], match["player_a2"]):
        db.execute("UPDATE tournament_player SET points = points + ? WHERE tournament_id = ? AND player_id = ?",
                   (net_a, match["tournament_id"], pid))
        db.execute("UPDATE player SET points = points + ? WHERE id = ?", (net_a, pid))

    for pid in (match["player_b1"], match["player_b2"]):
        db.execute("UPDATE tournament_player SET points = points + ? WHERE tournament_id = ? AND player_id = ?",
                   (net_b, match["tournament_id"], pid))
        db.execute("UPDATE player SET points = points + ? WHERE id = ?", (net_b, pid))

    db.commit()
    db.close()
    return jsonify({"ok": True})


@app.route("/api/db/download")
def download_db():
    return send_file(DB_PATH, as_attachment=True, download_name="americano.db")


@app.route("/api/db/upload", methods=["POST"])
@admin_required
def upload_db():
    f = request.files.get("file")
    if not f:
        return jsonify({"error": "No file uploaded"}), 400
    f.save(DB_PATH)
    return jsonify({"ok": True})


if __name__ == "__main__":
    import os
    init_db()
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(debug=debug, host="0.0.0.0", port=5000)
