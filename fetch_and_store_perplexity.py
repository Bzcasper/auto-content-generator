import requests
import os
import json
import uuid
from datetime import datetime, timezone
from pydantic import BaseModel, HttpUrl, ValidationError
from typing import List

# API Credentials (loaded from GitHub Secrets)
PERPLEXITY_API_KEY = os.getenv('PERPLEXITY_API_KEY')
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_API_KEY = os.getenv('SUPABASE_API_KEY')

# Supabase API Endpoints
SUPABASE_INSERT_URL = f"{SUPABASE_URL}/rest/v1/diy_trending_projects"
SUPABASE_STORAGE_URL = f"{SUPABASE_URL}/storage/v1/object"

# Generate a Unique File Name
today_date = datetime.today().strftime('%Y-%m-%d')
unique_id = str(uuid.uuid4())[:8]  # Short unique identifier
JSON_FILE_NAME = f"{unique_id}.json"
JSON_FILE_PATH = f"{today_date}/{JSON_FILE_NAME}"  # Store in date-based folder

# Pydantic Model for API Response Validation
class DIYProject(BaseModel):
    url: HttpUrl  # Ensures only valid URLs are processed

class DIYProjectsResponse(BaseModel):
    citations: List[DIYProject]  # Ensures Perplexity returns only URLs

# Step 1: Fetch Trending DIY Projects from Perplexity
def fetch_trending_diy_projects():
    headers = {
        'Authorization': f'Bearer {PERPLEXITY_API_KEY}',
        'Content-Type': 'application/json'
    }

    # Optimized Prompt: Exclude YouTube & Ensure Only Blogs/Webpages
    data = {
        'model': 'sonar-reasoning',
        'messages': [{
            'role': 'user', 
            'content': (
                "Provide exactly 20 URLs for trending DIY projects, friends & family crafts, and hobbies in 2025. "
                "Only include URLs from blogs, articles, and DIY-related websites. "
                "Strictly exclude URLs from YouTube, TikTok, Instagram, Pinterest, Twitter, and any other social media or video platforms. "
                "Make sure these links are from trusted DIY blogs and niche craft websites. "
                "Respond in JSON format as an array of URLs only, with no descriptions."
            )
        }],
        'max_tokens': 400,  # Increased to handle more URLs
        'temperature': 0.7
    }

    response = requests.post('https://api.perplexity.ai/chat/completions', json=data, headers=headers)
    
    if response.status_code != 200:
        print(f"❌ Perplexity API Error: {response.text}")
        return []

    result = response.json()
    
    try:
        validated_data = DIYProjectsResponse(**{"citations": [{"url": url} for url in result.get('citations', [])]})
        urls = [{"url": str(entry.url)} for entry in validated_data.citations]  # Convert HttpUrl to string
    except ValidationError as e:
        print(f"❌ Data validation error: {e}")
        return []

    # Save URLs locally in JSON format
    local_json_path = f"./{JSON_FILE_PATH}"
    os.makedirs(os.path.dirname(local_json_path), exist_ok=True)
    
    with open(local_json_path, "w", encoding="utf-8") as json_file:
        json.dump(urls, json_file, indent=4)
    
    print(f"✅ URLs saved locally at {local_json_path}")
    
    return urls, local_json_path

# Step 2: Upload JSON File to Supabase Storage
def upload_to_supabase_storage(local_json_path):
    headers = {
        'Authorization': f'Bearer {SUPABASE_API_KEY.strip()}',
        'apikey': f'{SUPABASE_API_KEY.strip()}',
        'Content-Type': 'application/json'
    }

    # Define the storage path inside Supabase Storage Bucket
    storage_path = f"url_bucket/{JSON_FILE_PATH}"

    with open(local_json_path, "rb") as file_data:
        response = requests.put(f"{SUPABASE_STORAGE_URL}/{storage_path}", headers=headers, data=file_data)

    if response.status_code in [200, 201]:
        print(f"✅ JSON file uploaded to Supabase Storage: {storage_path}")
    else:
        print(f"❌ Failed to upload JSON file: {response.text}")

# Step 3: Store Data in Supabase Database
def store_in_supabase(urls):
    headers = {
        'Authorization': f'Bearer {SUPABASE_API_KEY.strip()}',
        'apikey': f'{SUPABASE_API_KEY.strip()}',
        'Content-Type': 'application/json',
        'Prefer': 'return=minimal'
    }

    for entry in urls:
        data = {
            "title": "Trending DIY Project",
            "url": entry["url"],
            "created_at": datetime.now(timezone.utc).isoformat()  # Fixed deprecation warning
        }

        response = requests.post(SUPABASE_INSERT_URL, json=data, headers=headers)
        
        if response.status_code == 201:
            print(f"✅ Stored in Supabase: {entry['url']}")
        else:
            print(f"❌ Failed to store {entry['url']}: {response.text}")

# Step 4: Run the Script
def main():
    try:
        print("📡 Fetching trending DIY project URLs from Perplexity...")
        urls, local_json_path = fetch_trending_diy_projects()
        
        if urls:
            print("🛠 Uploading JSON to Supabase Storage...")
            upload_to_supabase_storage(local_json_path)

            print("🛠 Storing URLs in Supabase database...")
            store_in_supabase(urls)
        else:
            print("⚠️ No URLs found.")

    except Exception as e:
        print(f"❌ An error occurred: {e}")

if __name__ == '__main__':
    main()
