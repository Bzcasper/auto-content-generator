import asyncio
import json
from pathlib import Path
import subprocess
from crawler import DIYCrawler

# Configuration
SUPABASE_URL = "https://vaubsaaeexjdgzpzuqcm.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZhdWJzYWFlZXhqZGd6cHp1cWNtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3MzgzOTUwMTQsImV4cCI6MjA1Mzk3MTAxNH0.SBOAxBIGbaVRxmYo_ms5pfAKXpfBw2K8snPaa5T0ms8"
GROQ_API_KEY = "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"

# Create data directory
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

def check_playwright_installation():
    try:
        # Try to install browsers if they're not already installed
        subprocess.run(["playwright", "install"], check=True)
        subprocess.run(["playwright", "install-deps"], check=True)
        return True
    except Exception as e:
        print(f"Error installing Playwright dependencies: {str(e)}")
        return False

async def main():
    # Check Playwright installation
    if not check_playwright_installation():
        print("Failed to install Playwright dependencies. Please try running:")
        print("playwright install")
        print("playwright install-deps")
        return

    # Initialize crawler
    crawler = DIYCrawler(
        supabase_url=SUPABASE_URL,
        supabase_key=SUPABASE_KEY,
        api_key=GROQ_API_KEY
    )
    
    # Load URLs
    urls_file = DATA_DIR / "diy_urls.json"
    if not urls_file.exists():
        sample_urls = {
            "urls": [
                "https://www.instructables.com/Easy-Weekend-DIY-Projects/",
                "https://www.familyhandyman.com/list/beginner-woodworking-projects/"
            ]
        }
        urls_file.write_text(json.dumps(sample_urls, indent=2))
        print(f"Created sample URLs file at {urls_file}")

    # Load and validate URLs
    try:
        urls_data = json.loads(urls_file.read_text())
        urls = urls_data.get("urls", [])
        if not urls:
            raise ValueError("No URLs found in configuration file")
    except json.JSONDecodeError:
        raise ValueError(f"Invalid JSON in {urls_file}")

    # Process URLs with concurrency limit
    semaphore = asyncio.Semaphore(3)  # Limit concurrent requests
    
    async def process_url(url):
        async with semaphore:
            try:
                project = await crawler.extract_project(url)
                if project:
                    await crawler.store_project(project)
                    print(f"Successfully processed: {url}")
                else:
                    print(f"Failed to extract project from: {url}")
            except Exception as e:
                print(f"Error processing {url}: {str(e)}")

    # Process all URLs concurrently but with limits
    await asyncio.gather(*[process_url(url) for url in urls])

if __name__ == "__main__":
    asyncio.run(main())