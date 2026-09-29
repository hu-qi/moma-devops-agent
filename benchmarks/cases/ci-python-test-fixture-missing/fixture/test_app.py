import sys
from app import load_config, total_price


def test_total_price():
    data = load_config("data.json")
    result = total_price(data["items"])
    assert result == 60, f"Expected 60, got {result}"


if __name__ == "__main__":
    try:
        test_total_price()
        print("TESTS PASSED")
        sys.exit(0)
    except Exception as exc:
        sys.stderr.write(f"TESTS FAILED: {exc}\n")
        sys.exit(1)
