import json
import urllib.request


BASE_URL = "https://api.example.com"


def fetch_user(user_id: int) -> dict | None:
    try:
        url = f"{BASE_URL}/users/{user_id}"
        with urllib.request.urlopen(url, timeout=5) as resp:
            return json.loads(resp.read())
    except:
        pass
    return None


def update_user(user_id: int, payload: dict) -> bool:
    try:
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            f"{BASE_URL}/users/{user_id}",
            data=data,
            method="PUT",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except:
        pass
    return False


def delete_user(user_id: int) -> bool:
    try:
        req = urllib.request.Request(
            f"{BASE_URL}/users/{user_id}",
            method="DELETE",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 204
    except:
        pass
    return False
