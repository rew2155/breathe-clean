import random
import requests


pm25 = round(random.uniform(0, 100), 1)

reading = {
    "pm25": pm25
}

response = requests.post(
    "http://127.0.0.1:8000/readings",
    json=reading
)

print(response.status_code)
print(response.json())