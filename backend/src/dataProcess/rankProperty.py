import logging


GROWTH_SCORE = {
    "HIGH": 30,
    "MED": 20,
    "LOW": 10,
}


GROWTH_SCORE = {"HIGH": 30, "MED": 20, "LOW": 10}

def score_property(row: dict, budget: float) -> int:
    score = 0

    # budget fit (30pts) — how well price fits budget, penalise if too cheap or too close to limit
    if budget > 0:
        ratio = row["median_price"] / budget
        if 0.5 <= ratio <= 0.95:      # sweet spot — not too cheap, not too close to limit
            score += 30
        elif ratio < 0.5:              # suspiciously cheap
            score += 15
        elif ratio <= 1.0:             # very close to budget limit
            score += 10

    # transaction volume (40pts) — normalised, not arbitrary
    transactions = row.get("transactions", 0) or 0
    if transactions >= 200:    score += 40
    elif transactions >= 100:  score += 30
    elif transactions >= 50:   score += 20
    elif transactions >= 20:   score += 10

    # growth potential (30pts)
    growth = (row.get("growth_potential") or "").strip().upper()
    score += GROWTH_SCORE.get(growth, 0)

    return max(0, min(score, 100))


def rank_properties(properties: list[dict], budget: float, top_n: int = 5) -> list[dict]:
    """
    Scores each property and returns top_n ranked results.
    Adds a 'score' key to each property dict.
    """
    if not properties:
        logging.warning("RANK | ⚠️ No properties to rank")
        return []

    for prop in properties:
        prop["score"] = score_property(prop, budget)

    ranked = sorted(properties, key=lambda x: x["score"], reverse=True)
    top = ranked[:top_n]

    logging.info(f"RANK | ✅ Ranked {len(properties)} properties, returning top {len(top)}")
    return top