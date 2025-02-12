import os
from firecrawl import FirecrawlApp
from anthropic import Anthropic
import json
from typing import Dict, List, Optional
import asyncio
from datetime import datetime, timedelta
import pandas as pd

class DIYTrendScraper:
    def __init__(self, firecrawl_api_key: str, anthropic_api_key: str):
        self.firecrawl = FirecrawlApp(api_key=firecrawl_api_key)
        self.anthropic = Anthropic(api_key=anthropic_api_key)
        
    async def scrape_pinterest(self, query: str = "diy projects", limit: int = 100) -> List[Dict]:
        """Scrape trending DIY projects from Pinterest"""
        results = []
        try:
            # Use Firecrawl to scrape Pinterest search results
            response = await self.firecrawl.crawl_url(
                f"https://www.pinterest.com/search/pins/?q={query}",
                params={
                    "limit": limit,
                    "extractMetrics": True,
                    "waitForScroll": True
                }
            )
            
            # Extract pin data
            for item in response['data']:
                pin = {
                    "platform": "pinterest",
                    "title": item.get("title", ""),
                    "description": item.get("description", ""),
                    "saves": item.get("saves", 0),
                    "url": item.get("url", ""),
                    "image_url": item.get("image", ""),
                    "category": item.get("category", ""),
                    "engagement_score": float(item.get("saves", 0)) * 1.5
                }
                results.append(pin)
                
        except Exception as e:
            print(f"Error scraping Pinterest: {str(e)}")
            
        return results

    async def scrape_instagram(self, hashtags: List[str] = ["diy", "diycrafts", "diyprojects"]) -> List[Dict]:
        """Scrape trending DIY projects from Instagram"""
        results = []
        
        for hashtag in hashtags:
            try:
                response = await self.firecrawl.crawl_url(
                    f"https://www.instagram.com/explore/tags/{hashtag}/",
                    params={
                        "limit": 50,
                        "extractMetrics": True,
                        "waitForScroll": True
                    }
                )
                
                for post in response['data']:
                    item = {
                        "platform": "instagram", 
                        "hashtag": hashtag,
                        "caption": post.get("caption", ""),
                        "likes": post.get("likes", 0),
                        "comments": post.get("comments", 0),
                        "url": post.get("url", ""),
                        "image_url": post.get("image", ""),
                        "engagement_score": float(post.get("likes", 0)) + float(post.get("comments", 0)) * 2
                    }
                    results.append(item)
                    
            except Exception as e:
                print(f"Error scraping Instagram #{hashtag}: {str(e)}")
                
        return results

    async def scrape_tiktok(self, keywords: List[str] = ["diy", "diytutorial"]) -> List[Dict]:
        """Scrape trending DIY projects from TikTok"""
        results = []
        
        for keyword in keywords:
            try:
                response = await self.firecrawl.crawl_url(
                    f"https://www.tiktok.com/tag/{keyword}",
                    params={
                        "limit": 50,
                        "extractMetrics": True,
                        "waitForVideo": True
                    }
                )
                
                for video in response['data']:
                    item = {
                        "platform": "tiktok",
                        "keyword": keyword,
                        "description": video.get("description", ""),
                        "views": video.get("views", 0),
                        "likes": video.get("likes", 0),
                        "shares": video.get("shares", 0),
                        "comments": video.get("comments", 0),
                        "url": video.get("url", ""),
                        "thumbnail_url": video.get("thumbnail", ""),
                        "engagement_score": (float(video.get("likes", 0)) * 1 + 
                                          float(video.get("comments", 0)) * 2 + 
                                          float(video.get("shares", 0)) * 3)
                    }
                    results.append(item)
                    
            except Exception as e:
                print(f"Error scraping TikTok for {keyword}: {str(e)}")
                
        return results

    async def analyze_trends(self, all_results: List[Dict]) -> Dict:
        """Analyze trends across platforms"""
        
        # Convert to DataFrame for easier analysis
        df = pd.DataFrame(all_results)
        
        # Get top trending projects by engagement
        top_trends = df.nlargest(10, 'engagement_score')
        
        # Calculate platform distribution
        platform_dist = df['platform'].value_counts().to_dict()
        
        # Get average engagement by platform
        avg_engagement = df.groupby('platform')['engagement_score'].mean().to_dict()
        
        # Extract common keywords/themes using Claude
        descriptions = df['description'].tolist() if 'description' in df else df['caption'].tolist()
        
        prompt = f"""Analyze these DIY project descriptions and identify:
        1. Most common themes/categories
        2. Popular materials used
        3. Difficulty levels mentioned
        4. Seasonal trends if any
        
        Descriptions: {descriptions[:100]}
        
        Return response as JSON with these keys:
        themes, materials, difficulty_levels, seasonal_trends
        """
        
        response = self.anthropic.messages.create(
            model="claude-3-opus-20240229",
            max_tokens=1000,
            messages=[{
                "role": "user", 
                "content": prompt
            }]
        )
        
        theme_analysis = json.loads(response.content[0].text)
        
        return {
            "top_trending_projects": top_trends.to_dict('records'),
            "platform_distribution": platform_dist,
            "average_engagement": avg_engagement,
            "theme_analysis": theme_analysis,
            "total_projects_analyzed": len(df),
            "date_analyzed": datetime.now().isoformat()
        }

    async def run_full_analysis(self) -> Dict:
        """Run complete analysis across all platforms"""
        
        # Gather data from all platforms concurrently
        pinterest_results = await self.scrape_pinterest()
        instagram_results = await self.scrape_instagram()
        tiktok_results = await self.scrape_tiktok()
        
        # Combine all results
        all_results = pinterest_results + instagram_results + tiktok_results
        
        # Analyze trends
        trend_analysis = await self.analyze_trends(all_results)
        
        # Save results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        with open(f"diy_trends_{timestamp}.json", "w") as f:
            json.dump(trend_analysis, f, indent=2)
            
        return trend_analysis

async def main():
    # Initialize scraper
    scraper = DIYTrendScraper(
        firecrawl_api_key=os.getenv("FIRECRAWL_API_KEY"),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY")
    )
    
    # Run analysis
    trends = await scraper.run_full_analysis()
    
    print("Top 5 Trending DIY Projects:")
    for project in trends["top_trending_projects"][:5]:
        print(f"- {project.get('title', project.get('description', 'Untitled'))} "
              f"(Platform: {project['platform']}, "
              f"Engagement Score: {project['engagement_score']:.2f})")
              
    print("\nTheme Analysis:")
    for theme, count in trends["theme_analysis"]["themes"].items():
        print(f"- {theme}")

if __name__ == "__main__":
    asyncio.run(main())
