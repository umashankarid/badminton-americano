"""Americano pairing engine: round-robin schedule with optimal opponent distribution."""
from itertools import combinations, permutations
from collections import defaultdict
from random import shuffle, seed, sample, randint

# Pre-computed optimal templates for perfect opponent spread (2-2)
OPTIMAL_TEMPLATES = {
    (8, 2): [
        (0,1,2,3, 4,5,6,7),
        (0,2,4,7, 5,6,1,3),
        (0,4,1,5, 2,7,3,6),
        (0,5,2,6, 3,7,1,4),
        (0,3,5,7, 1,2,4,6),
        (0,6,3,4, 2,5,1,7),
        (0,7,1,6, 2,4,3,5),
    ],
    (9, 2): [
        (3,2,1,8, 4,5,7,6, 0),
        (2,0,4,6, 7,8,1,5, 3),
        (0,3,7,5, 1,6,4,8, 2),
        (4,7,8,0, 6,2,5,3, 1),
        (7,1,6,3, 5,0,8,2, 4),
        (1,4,5,2, 8,3,6,0, 7),
        (6,5,0,1, 3,7,2,4, 8),
        (5,8,3,4, 2,1,0,7, 6),
        (8,6,2,7, 0,4,3,1, 5),
    ],
}


def generate_full_schedule(player_ids, courts):
    """Generate the complete tournament schedule upfront.
    Returns list of rounds: [(matches, sitting_out), ...]
    where matches = [(a1,a2,b1,b2), ...]
    """
    n = len(player_ids)
    
    # Use optimal template if available
    key = (n, courts)
    if key in OPTIMAL_TEMPLATES:
        return _apply_template(player_ids, OPTIMAL_TEMPLATES[key], courts)
    
    # Otherwise use round-robin algorithm
    return _generate_round_robin(player_ids, courts)


def _apply_template(player_ids, template, courts):
    """Apply a pre-computed template to actual player IDs."""
    n = len(player_ids)
    # Shuffle player mapping for randomness
    mapping = list(range(n))
    shuffle(mapping)
    
    schedule = []
    for entry in template:
        if n == 8:
            a1,a2,b1,b2, c1,c2,d1,d2 = entry
            matches = [
                (player_ids[mapping[a1]], player_ids[mapping[a2]], player_ids[mapping[b1]], player_ids[mapping[b2]]),
                (player_ids[mapping[c1]], player_ids[mapping[c2]], player_ids[mapping[d1]], player_ids[mapping[d2]]),
            ]
            schedule.append((matches, []))
        elif n == 9:
            a1,a2,b1,b2, c1,c2,d1,d2, sit = entry
            matches = [
                (player_ids[mapping[a1]], player_ids[mapping[a2]], player_ids[mapping[b1]], player_ids[mapping[b2]]),
                (player_ids[mapping[c1]], player_ids[mapping[c2]], player_ids[mapping[d1]], player_ids[mapping[d2]]),
            ]
            schedule.append((matches, [player_ids[mapping[sit]]]))
    return schedule


def _generate_round_robin(player_ids, courts):
    """Generate schedule using round-robin with opponent optimization."""
    n = len(player_ids)
    players_per_round = courts * 4
    n_sit = n - players_per_round
    all_pairs = list(combinations(range(n), 2))
    
    # Try multiple seeds, pick best complete schedule
    best_schedule = None
    best_used = 0
    best_opp_max = float('inf')
    
    for attempt in range(30):
        seed(attempt + randint(0, 1000))
        pair_pool = list(all_pairs)
        shuffle(pair_pool)
        
        used_pairs = set()
        sit_counts = [0] * n
        rounds_of_pairs = []
        
        for _ in range(200):
            if len(used_pairs) >= len(all_pairs):
                break
            
            # Try multiple sit-out combos
            best_round = None
            for _ in range(8):
                if n_sit > 0:
                    sorted_p = sorted(range(n), key=lambda p: sit_counts[p])
                    shuffle_group = [p for p in sorted_p if sit_counts[p] == sit_counts[sorted_p[0]]]
                    shuffle(shuffle_group)
                    sorted_p = shuffle_group + [p for p in sorted_p if p not in shuffle_group]
                    sitting = sorted_p[:n_sit]
                    active = set(range(n)) - set(sitting)
                else:
                    active = set(range(n))
                    sitting = []
                
                available = [p for p in pair_pool if p not in used_pairs and p[0] in active and p[1] in active]
                round_pairs = []
                used_in_round = set()
                for p in available:
                    if p[0] in used_in_round or p[1] in used_in_round:
                        continue
                    round_pairs.append(p)
                    used_in_round.update(p)
                    if len(round_pairs) == courts * 2:
                        break
                
                if len(round_pairs) % 2 != 0:
                    round_pairs = round_pairs[:-1]
                
                if round_pairs and (not best_round or len(round_pairs) > len(best_round[0])):
                    best_round = (round_pairs, sitting)
            
            if not best_round or not best_round[0]:
                break
            
            rp, sitting = best_round
            for p in rp:
                used_pairs.add(p)
            for p in sitting:
                sit_counts[p] += 1
            rounds_of_pairs.append(best_round)
        
        if len(used_pairs) > best_used:
            best_used = len(used_pairs)
            # Build schedule with opponent optimization
            schedule = _assign_opponents(rounds_of_pairs, n)
            opp_counts = _count_opponents(schedule)
            opp_max = max(opp_counts.values()) if opp_counts else 0
            if opp_max < best_opp_max:
                best_opp_max = opp_max
                best_schedule = schedule
            if len(used_pairs) == len(all_pairs) and opp_max <= 3:
                break
    
    # Convert indices to actual player IDs
    if best_schedule:
        return [([(player_ids[a1], player_ids[a2], player_ids[b1], player_ids[b2]) for a1,a2,b1,b2 in matches],
                 [player_ids[p] for p in sitting]) for matches, sitting in best_schedule]
    return []


def _assign_opponents(rounds_of_pairs, n_players):
    """Assign which pairs play against which, minimizing opponent repetition."""
    schedule = []
    opp_counts = defaultdict(int)
    
    for round_pairs, sitting in rounds_of_pairs:
        if len(round_pairs) < 2:
            continue
        indices = list(range(len(round_pairs)))
        best_matches = None
        best_score = float('inf')
        
        # Try all permutations for small, sample for large
        if len(indices) <= 8:
            tried = set()
            for perm in permutations(indices):
                groups = tuple(sorted(tuple(sorted([perm[i], perm[i+1]])) for i in range(0, len(perm)-1, 2)))
                if groups in tried:
                    continue
                tried.add(groups)
                matches, score = _score_pairing(perm, round_pairs, opp_counts)
                if score < best_score:
                    best_score = score
                    best_matches = matches
        else:
            for _ in range(300):
                perm = list(indices)
                shuffle(perm)
                matches, score = _score_pairing(perm, round_pairs, opp_counts)
                if score < best_score:
                    best_score = score
                    best_matches = matches
        
        if best_matches:
            for a1, a2, b1, b2 in best_matches:
                for t1 in (a1, a2):
                    for t2 in (b1, b2):
                        opp_counts[(min(t1, t2), max(t1, t2))] += 1
            schedule.append((best_matches, sitting))
    
    return schedule


def _score_pairing(perm, round_pairs, opp_counts):
    matches = []
    score = 0
    for i in range(0, len(perm)-1, 2):
        pa = round_pairs[perm[i]]
        pb = round_pairs[perm[i+1]]
        matches.append((pa[0], pa[1], pb[0], pb[1]))
        for t1 in pa:
            for t2 in pb:
                score += opp_counts[(min(t1, t2), max(t1, t2))]
    return matches, score


def _count_opponents(schedule):
    opp = defaultdict(int)
    for matches, _ in schedule:
        for a1, a2, b1, b2 in matches:
            for t1 in (a1, a2):
                for t2 in (b1, b2):
                    opp[(min(t1, t2), max(t1, t2))] += 1
    return opp


# --- Legacy interface for app.py ---

def generate_round_pairings(player_ids, used_pairs, courts, player_points, sit_out_counts=None, prev_groups=None, opponent_counts=None):
    """Generate one round. Uses full schedule internally, returns round by round."""
    n = len(player_ids)
    current_round = len(used_pairs) // (courts * 2) + 1
    
    # Generate full schedule and return the requested round
    schedule = generate_full_schedule(player_ids, courts)
    
    if current_round > len(schedule):
        return None, []
    
    matches, sitting_out = schedule[current_round - 1]
    return matches, sitting_out


def get_used_pairs(db, tournament_id):
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
    rows = db.execute(
        "SELECT player_id, points FROM tournament_player WHERE tournament_id = ?",
        (tournament_id,)
    ).fetchall()
    return {r["player_id"]: r["points"] for r in rows}


def get_sit_out_counts(db, tournament_id):
    rows = db.execute(
        "SELECT player_id, sit_outs FROM tournament_player WHERE tournament_id = ?",
        (tournament_id,)
    ).fetchall()
    return {r["player_id"]: r["sit_outs"] for r in rows}


def get_prev_groups(db, tournament_id, current_round):
    if current_round <= 1:
        return []
    rows = db.execute(
        "SELECT player_a1, player_a2, player_b1, player_b2 FROM match WHERE tournament_id = ? AND round_num = ?",
        (tournament_id, current_round - 1)
    ).fetchall()
    return [{r["player_a1"], r["player_a2"], r["player_b1"], r["player_b2"]} for r in rows]


def get_opponent_counts(db, tournament_id):
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
