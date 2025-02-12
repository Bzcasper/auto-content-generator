import requests

url = "https://vaubsaaeexjdgzpzuqcm.supabase.co/functions/v1/trend-scraper"
headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer YOUR_SUPABASE_ANON_KEY"
}
payload = {"query": "DIY crafts"}

response = requests.post(url, json=payload, headers=headers)
data = response.json()
print(data)  # Output trending topics
