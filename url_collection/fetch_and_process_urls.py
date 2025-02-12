import asyncio
import aiohttp
import os
import json
from aiobotocore.session import get_session
from fetch import fetch_json  # Assuming this fetches data from a database

# API Endpoint for Firecrawl
FIRECRAWL_MAP_ENDPOINT = "https://api.firecrawl.com/map"

# Database Settings
DATABASE_BUCKET = os.getenv("DATABASE_BUCKET", "your-database-bucket")  # Change this if needed
URL_SOURCE_API = "https://your-database-endpoint.com/get_urls"  # Replace with your actual endpoint
RESULTS_SAVE_API = "https://your-database-endpoint.com/save_top_pages"  # Replace with your actual API

async def fetch_urls_from_db(session):
    """Fetch a list of URLs from the database."""
    return await fetch_json(session, URL_SOURCE_API)

async def fetch_firecrawl_data(session, url):
    """Fetch URL analysis from Firecrawl's map endpoint."""
    payload = {"url": url}
    async with session.post(FIRECRAWL_MAP_ENDPOINT, json=payload) as response:
        if response.status == 200:
            data = await response.json()
            return data.get("pages", [])
        else:
            print(f"Error fetching data for {url}: {response.status}")
            return []

async def get_top_traffic_pages(session, url):
    """Process Firecrawl data to find the top 3 highest-traffic pages."""
    pages = await fetch_firecrawl_data(session, url)
    if not pages:
        return {"url": url, "top_pages": []}
    
    # Sort pages by traffic and select top 3
    top_pages = sorted(pages, key=lambda x: x.get("traffic", 0), reverse=True)[:3]
    return {"url": url, "top_pages": top_pages}

async def save_results_to_db(session, data):
    """Save processed results back to the database."""
    async with session.post(RESULTS_SAVE_API, json={"results": data}) as response:
        if response.status == 200:
            print("Successfully saved results to the database.")
        else:
            print(f"Failed to save results: {response.status}")

async def process_urls():
    """Main function to process URLs from DB and save top pages."""
    session = get_session()

    async with aiohttp.ClientSession() as http_session:
        # Fetch URLs from the database
        url_list = await fetch_urls_from_db(http_session)
        if not url_list:
            print("No URLs found in the database.")
            return

        # Process each URL
        tasks = [get_top_traffic_pages(http_session, url) for url in url_list]
        results = await asyncio.gather(*tasks)

        # Save results back to the database
        await save_results_to_db(http_session, results)

if __name__ == "__main__":
    asyncio.run(process_urls())
