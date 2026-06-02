import logging


GROWTH_SCORE = {
    "HIGH": 30,
    "MED": 20,
    "LOW": 10,
}


def score_property(row: dict, budget: float) -> int:
    """
    Scores a property out of 100 based on:
    - Budget efficiency (40pts) — how far below budget the price is
    - Transaction volume  (30pts) — market demand indicator
    - Growth potential   (30pts) — LOW/MED/HIGH label from enrichment
    """
    score = 0

    # budget efficiency — cheaper relative to budget = higher score
    if budget > 0:
        budget_efficiency = 1 - (row["median_price"] / budget)
        score += int(budget_efficiency * 40)

    # transaction volume — capped at 30pts
    score += min(row.get("transactions", 0) // 10, 30)

    # growth potential
    growth = (row.get("growth_potential") or "").strip().upper()
    score += GROWTH_SCORE.get(growth, 0)

    return max(0, min(score, 100))  # clamp between 0-100


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