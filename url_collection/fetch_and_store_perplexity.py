import requests
import os
import json
from datetime import datetime

# API Credentials (Load from GitHub Secrets or .env file)
PERPLEXITY_API_KEY = os.getenv('PERPLEXITY_API_KEY')
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_API_KEY = os.getenv('SUPABASE_API_KEY')

# Supabase API Endpoint for inserting data
SUPABASE_INSERT_URL = f"{SUPABASE_URL}/rest/v1/diy_trending_projects"

# Fetch Trending DIY Projects from Perplexity
def fetch_trending_diy_projects():
    headers = {
        'Authorization': f'Bearer {PERPLEXITY_API_KEY}',
        'Content-Type': 'application/json'
    }
    data = {
        'model': 'sonar-reasoning',
        'messages': [{'role': 'user', 'content': 'What are the top 20 trending DIY projects?'}],
        'max_tokens': 250,
        'temperature': 0.7
    }
    response = requests.post('https://api.perplexity.ai/chat/completions', json=data, headers=headers)
    response.raise_for_status()
    result = response.json()

    # Extract top 20 URLs and titles
    projects = []
    for citation in result.get('citations', [])[:20]:
        projects.append({
            "title": citation.get("title", "Unknown Title"),
            "url": citation["url"]
        })

    return projects

# Store Data in Supabase
def store_in_supabase(projects):
    headers = {
        'Authorization': f'Bearer {SUPABASE_API_KEY}',
        'Content-Type': 'application/json',
        'Prefer': 'return=minimal'
    }

    for project in projects:
        data = {
            "title": project["title"],
            "url": project["url"],
            "created_at": datetime.utcnow().isoformat()
        }
        response = requests.post(SUPABASE_INSERT_URL, json=data, headers=headers)
        if response.status_code == 201:
            print(f"✅ Stored: {project['title']}")
        else:
            print(f"❌ Failed to store {project['title']}: {response.text}")

# Main Execution
def main():
    try:
        projects = fetch_trending_diy_projects()
        if projects:
            store_in_supabase(projects)
        else:
            print("⚠️ No projects found.")
    except Exception as e:
        print(f"❌ An error occurred: {e}")

if __name__ == '__main__':
    main()
