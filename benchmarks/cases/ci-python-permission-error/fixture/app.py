import os


def save_report(data, path="/readonly/report.txt"):
    """Save report data to the specified path."""
    with open(path, "w") as f:
        f.write(data)
    return {"status": "saved", "path": path}
