import os
import json
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime
import asyncio
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from concurrent.futures import ThreadPoolExecutor
from textblob import TextBlob

# Initialize Lambda Powertools
logger = Logger()
metrics = Metrics()
tracer = Tracer()

@dataclass
class TrendingVideo:
    video_id: str
    title: str
    description: str
    thumbnail_url: str
    view_count: int
    like_count: int
    comment_count: int
    engagement_score: float
    sentiment_score: float
    category: str
    published_at: str

class YouTubeTrendAnalyzer:
    def __init__(self, api_key: str):
        self.youtube = build('youtube', 'v3', developerKey=api_key)
        self.categories = ['DIY', 'Crafts', 'HomeImprovement', 'Woodworking']
        
    def calculate_engagement(self, stats: Dict) -> float:
        """Optimized engagement score calculation"""
        views = int(stats.get('viewCount', 0))
        likes = int(stats.get('likeCount', 0))
        comments = int(stats.get('commentCount', 0))
        
        if views == 0:
            return 0.0
            
        normalized_score = (
            (views / max(views, 1)) * 0.5 +
            (likes / max(views, 1)) * 0.3 +
            (comments / max(views, 1)) * 0.2
        )
        return round(normalized_score, 3)

    def quick_sentiment(self, text: str) -> float:
        """Fast sentiment analysis"""
        try:
            return TextBlob(text).sentiment.polarity
        except:
            return 0.0

    def get_video_details(self, video_id: str) -> Optional[Dict]:
        """Fetch detailed video information"""
        try:
            video_response = self.youtube.videos().list(
                part='snippet,statistics',
                id=video_id
            ).execute()

            if not video_response.get('items'):
                return None

            video = video_response['items'][0]
            snippet = video['snippet']
            statistics = video['statistics']

            return {
                'video_id': video_id,
                'title': snippet['title'],
                'description': snippet['description'],
                'thumbnail_url': snippet['thumbnails']['high']['url'],
                'statistics': statistics,
                'published_at': snippet['publishedAt'],
                'category_id': snippet['categoryId']
            }
        except HttpError as e:
            logger.error(f"Error fetching video details: {e}")
            return None

    def search_trending_videos(self, category: str, max_results: int = 10) -> List[Dict]:
        """Search for trending videos in a category"""
        try:
            search_response = self.youtube.search().list(
                q=f'{category} projects',
                part='id',
                type='video',
                order='viewCount',
                maxResults=max_results,
                relevanceLanguage='en'
            ).execute()

            video_ids = [item['id']['videoId'] for item in search_response.get('items', [])]
            
            with ThreadPoolExecutor(max_workers=5) as executor:
                video_details = list(filter(None, executor.map(
                    self.get_video_details, video_ids
                )))
            
            return video_details

        except HttpError as e:
            logger.error(f"Error searching videos: {e}")
            return []

    def discover_trends(self, max_results: int = 20) -> List[TrendingVideo]:
        """Main trend discovery method"""
        all_trends = []
        
        for category in self.categories:
            videos = self.search_trending_videos(category, max_results=5)
            
            for video in videos:
                stats = video['statistics']
                engagement_score = self.calculate_engagement(stats)
                sentiment_score = self.quick_sentiment(video['title'])
                
                trend = TrendingVideo(
                    video_id=video['video_id'],
                    title=video['title'],
                    description=video['description'],
                    thumbnail_url=video['thumbnail_url'],
                    view_count=int(stats.get('viewCount', 0)),
                    like_count=int(stats.get('likeCount', 0)),
                    comment_count=int(stats.get('commentCount', 0)),
                    engagement_score=engagement_score,
                    sentiment_score=sentiment_score,
                    category=category,
                    published_at=video['published_at']
                )
                all_trends.append(trend)
        
        # Sort by engagement score and return top results
        all_trends.sort(key=lambda x: x.engagement_score, reverse=True)
        return all_trends[:max_results]

@logger.inject_lambda_context
@metrics.log_metrics
@tracer.capture_lambda_handler
def lambda_handler(event, context):
    """Lambda handler for YouTube trend discovery"""
    try:
        youtube_api_key = os.environ.get('YOUTUBE_API_KEY')
        if not youtube_api_key:
            raise ValueError("YouTube API key not configured")

        analyzer = YouTubeTrendAnalyzer(youtube_api_key)
        trending_videos = analyzer.discover_trends(max_results=20)
        
        # Convert to serializable format
        trends_data = [
            {
                'video_id': t.video_id,
                'title': t.title,
                'thumbnail_url': t.thumbnail_url,
                'view_count': t.view_count,
                'engagement_score': t.engagement_score,
                'sentiment_score': t.sentiment_score,
                'category': t.category,
                'published_at': t.published_at
            }
            for t in trending_videos
        ]

        metrics.add_metric(name="ProcessedVideos", value=len(trends_data))
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'trends': trends_data,
                'timestamp': datetime.utcnow().isoformat()
            }),
            'headers': {
                'Content-Type': 'application/json'
            }
        }

    except Exception as e:
        logger.exception("Error processing YouTube trends")
        metrics.add_metric(name="ProcessingErrors", value=1)
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            }),
            'headers': {
                'Content-Type': 'application/json'
            }
        }
