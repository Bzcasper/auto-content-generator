import requests
from bs4 import BeautifulSoup
from supabase import create_client, Client

# Supabase Config
SUPABASE_URL = "https://your-supabase-url.supabase.co"
SUPABASE_KEY = "your-anon-key"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Scrape Example Website
def scrape_data():
    url = "https://example.com/news"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")

    # Extract Data (Modify for Your Needs)
    articles = soup.find_all("h2")
    data = [{"title": article.text} for article in articles]

    return data

# Save to Supabase
def save_to_supabase(data):
    response = supabase.table("content").insert(data).execute()
    print("Data Saved:", response)

# Run Scraper
if __name__ == "__main__":
    scraped_data = scrape_data()
    save_to_supabase(scraped_data)
