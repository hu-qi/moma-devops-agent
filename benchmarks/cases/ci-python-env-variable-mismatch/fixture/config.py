import os


def get_port() -> int:
    # Defect: reads from APP_PORT_NUM instead of APP_PORT specified by CI
    return int(os.environ.get("APP_PORT_NUM", 0))
