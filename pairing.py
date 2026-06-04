"""Pairing engine: rotate partners, balance opponents by points, handle sit-outs."""
from itertools import combinations
from random import shuffle


def generate_all_partnerships(player_ids):
    """Return all possible partner pairs from player list."""
    return list(combinations(player_ids, 2))


def generate_round_pairings(player_ids, used_pairs, courts, player_points, sit_out_counts=None):
    """Generate one round of matches.

    - Handles non-divisible-by-4 player counts by sitting out players.
    - Players who have sat out least get priority to play.
    - Partners are chosen from unused pairs (rotate everyone with everyone).
    - Opponents are balanced by combined team points.
    - Returns (matches, sitting_out): matches=[(a1, a2, b1, b2), ...], sitting_out=[player_ids]
    """
    if sit_out_counts is None:
        sit_out_counts = {pid: 0 for pid in player_ids}

    n = len(player_ids)
    max_playing = courts * 4

    # Determine who sits out: players who have sat out the MOST get priority to play
    if n > max_playing:
        sorted_players = sorted(player_ids, key=lambda p: sit_out_counts.get(p, 0), reverse=True)
        active_players = sorted_players[:max_playing]
        sitting_out = sorted_players[max_playing:]
    elif n % 4 != 0:
        num_sit = n % 4
        sorted_players = sorted(player_ids, key=lambda p: sit_out_counts.get(p, 0), reverse=True)
        active_players = sorted_players[:len(player_ids) - num_sit]
        sitting_out = sorted_players[len(player_ids) - num_sit:]
    else:
        active_players = player_ids
        sitting_out = []

    available_pairs = [p for p in generate_all_partnerships(active_players) if p not in used_pairs]
    if not available_pairs:
        return None, sitting_out

    # Sort available pairs by combined points for balanced pairing, or random for round 1
    if player_points and any(v != 0 for v in player_points.values()):
        available_pairs.sort(key=lambda p: player_points.get(p[0], 0) + player_points.get(p[1], 0), reverse=True)
    else:
        shuffle(available_pairs)

    # Greedily select non-overlapping pairs to fill courts*2 team slots
    selected_teams = []
    used_in_round = set()
    for pair in available_pairs:
        if pair[0] in used_in_round or pair[1] in used_in_round:
            continue
        selected_teams.append(pair)
        used_in_round.update(pair)
        if len(selected_teams) == courts * 2:
            break

    if len(selected_teams) < 2:
        return None, sitting_out

    # Ensure even number of teams
    if len(selected_teams) % 2 != 0:
        selected_teams = selected_teams[:-1]

    # Sort teams by combined points for balanced matchups
    selected_teams.sort(key=lambda p: player_points.get(p[0], 0) + player_points.get(p[1], 0))

    # Pair adjacent teams (closest in points) as opponents
    matches = []
    for i in range(0, len(selected_teams), 2):
        team_a = selected_teams[i]
        team_b = selected_teams[i + 1]
        matches.append((team_a[0], team_a[1], team_b[0], team_b[1]))

    return matches, sitting_out


def get_used_pairs(db, tournament_id):
    """Get all partner pairs already used in this tournament."""
    rows = db.execute(
        "SELECT player_a1, player_a2, player_b1, player_b2 FROM match WHERE tournament_id = ?",
        (tournament_id,)
    ).fetchall()
    used = set()
    for r in rows:
        used.add((min(r[0], r[1]), max(r[0], r[1])))
        used.add((min(r[2], r[3]), max(r[2], r[3])))
    return used


def get_tournament_points(db, tournament_id):
    """Get current points for all players in tournament."""
    rows = db.execute(
        "SELECT player_id, points FROM tournament_player WHERE tournament_id = ?",
        (tournament_id,)
    ).fetchall()
    return {r["player_id"]: r["points"] for r in rows}


def get_sit_out_counts(db, tournament_id):
    """Get how many times each player has sat out."""
    rows = db.execute(
        "SELECT player_id, sit_outs FROM tournament_player WHERE tournament_id = ?",
        (tournament_id,)
    ).fetchall()
    return {r["player_id"]: r["sit_outs"] for r in rows}
