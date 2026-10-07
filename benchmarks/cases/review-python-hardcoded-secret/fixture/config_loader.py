import requests


API_KEY = "sk-proj-REAL-KEY-1234567890abcdef"
BASE_URL = "https://api.example.com/v1"


def get_config():
    headers = {"Authorization": f"Bearer {API_KEY}"}
    response = requests.get(f"{BASE_URL}/config", headers=headers)
    response.raise_for_status()
    return response.json()


def update_config(payload: dict):
    headers = {"Authorization": f"Bearer {API_KEY}"}
    response = requests.put(f"{BASE_URL}/config", json=payload, headers=headers)
    response.raise_for_status()
    return response.json()
