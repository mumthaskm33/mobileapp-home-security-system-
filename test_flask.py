import app
import json

client = app.app.test_client()

try:
    print("Sending GET /api/history...")
    response = client.get('/api/history')
    print(f"Status Code: {response.status_code}")
    print(f"Data: {response.get_data(as_text=True)}")
except Exception as e:
    print(f"ERROR: {e}")
