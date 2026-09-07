import requests

data = {
    "system1": {
        "active": True,
        "elapsed": "00:12:30",
        "cost": 5000,
        "note": "PUBG"
    }
}

try:
    r = requests.post(
        "https://gamenet-server.onrender.com/update/hamid01",
        json=data,
        timeout=5
    )
    print("وضعیت:", r.status_code)
    print("پاسخ سرور:", r.text)
except Exception as e:
    print("خطا در ارسال:", e)