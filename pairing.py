"""Pairing engine: rotate partners, balance opponents by points, handle sit-outs."""
from itertools import combinations
from random import shuffle, sample


def generate_all_partnerships(player_ids):
    """Return all possible partner pairs from player list."""
    return list(combinations(sorted(player_ids), 2))


def generate_round_pairings(player_ids, used_pairs, courts, player_points, sit_out_counts=None, prev_groups=None, opponent_counts=None):
    """Generate one round of matches.

    - Handles non-divisible-by-4 player counts by sitting out players.
    - Players who have sat out the MOST get priority to play.
    - Partners are chosen from unused pairs (rotate everyone with everyone).
    - Opponents are balanced by combined team points.
    - Avoids putting same 4 players on same court as previous round.
    - Spreads opponents evenly (avoids same pair facing each other repeatedly).
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
        active_players = sorted_players[:n - num_sit]
        sitting_out = sorted_players[n - num_sit:]
    else:
        active_players = list(player_ids)
        sitting_out = []

    # Find valid matches: pick pairs of unused partnerships that form a complete match (4 distinct players)
    available_pairs = [p for p in generate_all_partnerships(active_players) if p not in used_pairs]
    if not available_pairs:
        return None, sitting_out

    # Try to find the best set of matches for this round
    # A match = 2 unused pairs with 4 distinct players
    best_matches = _find_matches(available_pairs, courts, player_points, prev_groups or [], opponent_counts or {})

    if not best_matches:
        return None, sitting_out

    return best_matches, sitting_out


def _find_matches(available_pairs, courts, player_points, prev_groups, opponent_counts):
    """Find up to `courts` matches, maximizing court usage and player mixing."""
    candidates = []
    prev_group_sets = [frozenset(g) for g in prev_groups]

    seen = set()
    for pair_a in available_pairs:
        for pair_b in available_pairs:
            if pair_b <= pair_a:
                continue
            four = {pair_a[0], pair_a[1], pair_b[0], pair_b[1]}
            if len(four) == 4:
                key = (pair_a, pair_b)
                if key not in seen:
                    seen.add(key)
                    team_a_pts = player_points.get(pair_a[0], 0) + player_points.get(pair_a[1], 0)
                    team_b_pts = player_points.get(pair_b[0], 0) + player_points.get(pair_b[1], 0)
                    balance = abs(team_a_pts - team_b_pts)
                    # Penalize same 4 players grouped together as previous round
                    group_penalty = 1000 if frozenset(four) in prev_group_sets else 0
                    # Penalize repeated opponents (sum of how often each cross-team pair faced each other)
                    opp_penalty = 0
                    for t1 in pair_a:
                        for t2 in pair_b:
                            k = (min(t1, t2), max(t1, t2))
                            opp_penalty += opponent_counts.get(k, 0) * 50
                    candidates.append((pair_a, pair_b, balance + group_penalty + opp_penalty))

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[2])

    best = _greedy_select(candidates, courts)

    if len(best) < courts and len(candidates) >= courts:
        from random import shuffle as rshuffle
        for _ in range(200):
            rshuffle(candidates)
            attempt = _greedy_select(candidates, courts)
            if len(attempt) > len(best):
                best = attempt
            if len(best) == courts:
                break

    return best if best else None


def _greedy_select(candidates, courts):
    matches = []
    used_players = set()
    used_pairs_in_round = set()
    for pair_a, pair_b, _ in candidates:
        four = {pair_a[0], pair_a[1], pair_b[0], pair_b[1]}
        if four & used_players:
            continue
        if pair_a in used_pairs_in_round or pair_b in used_pairs_in_round:
            continue
        matches.append((pair_a[0], pair_a[1], pair_b[0], pair_b[1]))
        used_players.update(four)
        used_pairs_in_round.add(pair_a)
        used_pairs_in_round.add(pair_b)
        if len(matches) == courts:
            break
    return matches


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


def get_prev_groups(db, tournament_id, current_round):
    """Get the groups of 4 players from the previous round."""
    if current_round <= 1:
        return []
    rows = db.execute(
        "SELECT player_a1, player_a2, player_b1, player_b2 FROM match WHERE tournament_id = ? AND round_num = ?",
        (tournament_id, current_round - 1)
    ).fetchall()
    return [{r["player_a1"], r["player_a2"], r["player_b1"], r["player_b2"]} for r in rows]


def get_opponent_counts(db, tournament_id):
    """Get how many times each pair of players have been opponents."""
    rows = db.execute(
        "SELECT player_a1, player_a2, player_b1, player_b2 FROM match WHERE tournament_id = ?",
        (tournament_id,)
    ).fetchall()
    counts = {}
    for r in rows:
        for t1 in (r["player_a1"], r["player_a2"]):
            for t2 in (r["player_b1"], r["player_b2"]):
                k = (min(t1, t2), max(t1, t2))
                counts[k] = counts.get(k, 0) + 1
    return counts
