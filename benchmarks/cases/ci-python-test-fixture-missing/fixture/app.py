import json


def load_config(path="data.json"):
    with open(path, "r") as f:
        return json.load(f)


def total_price(items):
    return sum(item["price"] * item["qty"] for item in items)
