import logging

GROWTH_SCORE = {
    "HIGH": 30,
    "MED": 20,
    "LOW": 10,
}

PRIORITY_WEIGHTS = {
    "balanced": {
        "budget": 30,
        "transactions": 40,
        "growth": 30,
    },
    "lowest_price": {
        "budget": 50,
        "transactions": 25,
        "growth": 25,
    },
    "market_activity": {
        "budget": 20,
        "transactions": 60,
        "growth": 20,
    },
    "growth_potential": {
        "budget": 20,
        "transactions": 25,
        "growth": 55,
    },
}


def get_budget_raw_score(row: dict, budget: float) -> float:
    if budget <= 0:
        return 0

    ratio = row["median_price"] / budget

    if 0.5 <= ratio <= 0.95:
        return 1.0
    elif ratio < 0.5:
        return 0.5
    elif ratio <= 1.0:
        return 0.33

    return 0


def get_transaction_raw_score(row: dict) -> float:
    transactions = row.get("transactions", 0) or 0

    if transactions >= 200:
        return 1.0
    elif transactions >= 100:
        return 0.75
    elif transactions >= 50:
        return 0.5
    elif transactions >= 20:
        return 0.25

    return 0


def get_growth_raw_score(row: dict) -> float:
    growth = (row.get("growth_potential") or "").strip().upper()

    if growth == "HIGH":
        return 1.0
    elif growth == "MED":
        return 0.67
    elif growth == "LOW":
        return 0.33

    return 0


def score_property(row: dict, budget: float, priority: str = "balanced") -> int:
    weights = PRIORITY_WEIGHTS.get(priority, PRIORITY_WEIGHTS["balanced"])

    budget_score = get_budget_raw_score(row, budget) * weights["budget"]
    transaction_score = get_transaction_raw_score(row) * weights["transactions"]
    growth_score = get_growth_raw_score(row) * weights["growth"]

    score = budget_score + transaction_score + growth_score

    return round(max(0, min(score, 100)))


def rank_properties(properties: list[dict], budget: float, priority: str = "balanced", top_n: int = 5) -> list[dict]:

    if not properties:
        logging.warning("RANK | ⚠️ No properties to rank")
        return []

    for prop in properties:
        prop["score"] = score_property(prop, budget, priority)

    ranked = sorted(properties, key=lambda x: x["score"], reverse=True)
    top = ranked[:top_n]

    logging.info(
        f"RANK | ✅ Ranked {len(properties)} properties with priority={priority}, returning top {len(top)}"
    )

    return top