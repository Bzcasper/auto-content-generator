import asyncio
from datetime import datetime
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, HttpUrl
from asyncio import AsyncIOMotorClient
import aiohttp
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
import uuid
import logging

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
formatter = logging.Formatter("[%(asctime)s] %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)


class ContentMetrics(BaseModel):
    """Content performance and engagement metrics"""
    engagement_score: float
    virality_potential: float
    audience_fit: float
    optimal_posting_times: Dict[str, str]
    hashtag_recommendations: List[str]
    content_quality_score: float


class ContentItem(BaseModel):
    """Core content model"""
    id: str
    url: HttpUrl
    title: str
    content: str
    summary: str
    metrics: ContentMetrics
    created_at: datetime
    target_platforms: List[str]
    content_type: str
    category: str


class ContentFlowCore:
    """Core service for content analysis and optimization"""

    def __init__(self):
        self.crawler = AsyncWebCrawler(verbose=True)
        self.vectorizer = TfidfVectorizer(max_features=1000)
        self.content_cache = {}  # Cache for storing previously processed content for originality checks

    async def analyze_content(self, url: str, target_platforms: List[str], content_type: str) -> ContentItem:
        """Analyze and optimize content for target platforms"""
        config = CrawlerRunConfig(
            markdown_generator=DefaultMarkdownGenerator(
                content_filter=PruningContentFilter(
                    threshold=0.4,
                    min_word_threshold=50
                )
            ),
            excluded_tags=['nav', 'footer', 'aside'],
            remove_overlay_elements=True
        )

        try:
            # Crawl and extract content
            result = await self.crawler.arun(url=url, config=config)
        except Exception as e:
            logger.error(f"Error crawling URL {url}: {e}")
            raise e

        # Generate content metrics
        metrics = await self._generate_content_metrics(
            content=result.markdown_v2.fit_markdown,
            platforms=target_platforms,
            content_type=content_type
        )

        content_item = ContentItem(
            id=str(uuid.uuid4()),
            url=url,
            title=result.metadata.get('title', 'Untitled'),
            content=result.markdown_v2.fit_markdown,
            summary=result.metadata.get('description', '')[:500],
            metrics=metrics,
            created_at=datetime.now(),
            target_platforms=target_platforms,
            content_type=content_type,
            category=self._determine_category(result.markdown_v2.fit_markdown)
        )

        # Cache the content for originality checks
        self.content_cache[content_item.id] = content_item.content
        logger.info(f"Content analyzed and generated for URL: {url}")
        return content_item

    async def _generate_content_metrics(
        self,
        content: str,
        platforms: List[str],
        content_type: str
    ) -> ContentMetrics:
        """Generate comprehensive content metrics"""
        # Calculate base metrics
        word_count = len(content.split())
        sentences = content.split('.')
        avg_sentence_length = word_count / len(sentences) if sentences else 0

        # Platform-specific optimizations
        platform_scores = {
            "twitter": self._calculate_twitter_score(content),
            "linkedin": self._calculate_linkedin_score(content, content_type),
            "instagram": self._calculate_instagram_score(content)
        }

        # Calculate engagement potential
        engagement_score = np.mean([score for score in platform_scores.values()])

        # Generate optimal posting times
        posting_times = self._get_optimal_posting_times(platforms)

        # Generate hashtag recommendations
        hashtags = await self._generate_hashtags(content, content_type)

        return ContentMetrics(
            engagement_score=engagement_score,
            virality_potential=self._calculate_virality_potential(content),
            audience_fit=self._calculate_audience_fit(content, platforms),
            optimal_posting_times=posting_times,
            hashtag_recommendations=hashtags,
            content_quality_score=self._calculate_quality_score(content)
        )

    def _calculate_twitter_score(self, content: str) -> float:
        """Calculate Twitter-specific engagement score"""
        word_count = len(content.split())
        ideal_length = 250  # Optimal tweet length
        length_score = 1 - min(abs(word_count - ideal_length) / ideal_length, 1)

        # Check for engagement triggers
        has_question = '?' in content
        has_call_to_action = any(cta in content.lower() for cta in ['follow', 'retweet', 'like', 'share'])

        base_score = length_score * 0.5
        if has_question:
            base_score += 0.2
        if has_call_to_action:
            base_score += 0.3

        return min(base_score, 1.0)

    def _calculate_linkedin_score(self, content: str, content_type: str) -> float:
        """Calculate LinkedIn-specific engagement score"""
        word_count = len(content.split())

        # Different ideal lengths for different content types
        ideal_lengths = {
            "article": 1500,
            "post": 800,
            "update": 200
        }
        ideal_length = ideal_lengths.get(content_type, 800)

        length_score = 1 - min(abs(word_count - ideal_length) / ideal_length, 1)

        # Check for professional tone and structure
        has_paragraphs = len(content.split('\n\n')) > 1
        has_professional_terms = any(term in content.lower() for term in
                                     ['experience', 'professional', 'industry', 'business', 'strategy'])

        base_score = length_score * 0.4
        if has_paragraphs:
            base_score += 0.3
        if has_professional_terms:
            base_score += 0.3

        return min(base_score, 1.0)

    def _calculate_instagram_score(self, content: str) -> float:
        """Calculate Instagram-specific engagement score"""
        word_count = len(content.split())
        ideal_length = 150  # Optimal Instagram caption length
        length_score = 1 - min(abs(word_count - ideal_length) / ideal_length, 1)

        # Check for engagement elements
        has_emoji = any(char in content for char in ['😀', '🎉', '🔥', '❤️'])  # basic emoji check
        has_story_element = len(content.split('\n\n')) > 1

        base_score = length_score * 0.4
        if has_emoji:
            base_score += 0.3
        if has_story_element:
            base_score += 0.3

        return min(base_score, 1.0)

    def _calculate_virality_potential(self, content: str) -> float:
        """Calculate potential for content to go viral"""
        features = {
            'emotion': self._detect_emotional_content(content),
            'shareability': self._calculate_shareability(content),
            'uniqueness': self._calculate_uniqueness(content),
            'timeliness': self._check_timeliness(content)
        }

        weights = {'emotion': 0.3, 'shareability': 0.3, 'uniqueness': 0.2, 'timeliness': 0.2}
        virality_score = sum(score * weights[feature] for feature, score in features.items())

        return min(virality_score, 1.0)

    def _calculate_audience_fit(self, content: str, platforms: List[str]) -> float:
        """Calculate how well content matches target audience"""
        platform_weights = {
            "twitter": 0.35,
            "linkedin": 0.35,
            "instagram": 0.3
        }

        scores = []
        for platform in platforms:
            if platform == "twitter":
                scores.append(self._calculate_twitter_score(content))
            elif platform == "linkedin":
                scores.append(self._calculate_linkedin_score(content, "post"))
            elif platform == "instagram":
                scores.append(self._calculate_instagram_score(content))

        if not scores:
            return 0.5

        # Weight each platform score according to predefined platform weights
        weighted_scores = [
            score * platform_weights.get(platform, 0.33)
            for score, platform in zip(scores, platforms)
        ]
        return sum(weighted_scores) / len(weighted_scores)

    async def _generate_hashtags(self, content: str, content_type: str) -> List[str]:
        """Generate relevant hashtags based on content"""
        # Extract key terms using TF-IDF
        tfidf_matrix = self.vectorizer.fit_transform([content])
        feature_names = self.vectorizer.get_feature_names_out()

        # Get top terms based on TF-IDF scores
        scores = zip(feature_names, tfidf_matrix.toarray()[0])
        sorted_scores = sorted(scores, key=lambda x: x[1], reverse=True)

        # Convert top terms to hashtags
        hashtags = [f"#{term}" for term, _ in sorted_scores[:5]]

        # Add content type specific hashtags
        type_hashtags = {
            "article": ["#article", "#blog", "#reading"],
            "social_post": ["#social", "#trending", "#viral"],
            "news": ["#news", "#update", "#latest"]
        }

        hashtags.extend(type_hashtags.get(content_type, [])[:2])
        return hashtags[:7]  # Return top 7 hashtags

    def _get_optimal_posting_times(self, platforms: List[str]) -> Dict[str, str]:
        """Get optimal posting times for each platform"""
        base_times = {
            "twitter": {
                "weekday": "12:00-15:00",
                "weekend": "9:00-11:00"
            },
            "linkedin": {
                "weekday": "8:00-10:00",
                "weekend": "10:00-11:00"
            },
            "instagram": {
                "weekday": "11:00-13:00",
                "weekend": "9:00-11:00"
            }
        }

        current_day = datetime.now().strftime("%A")
        is_weekend = current_day in ["Saturday", "Sunday"]

        return {
            platform: base_times[platform]["weekend" if is_weekend else "weekday"]
            for platform in platforms if platform in base_times
        }

    def _calculate_quality_score(self, content: str) -> float:
        """Calculate overall content quality score"""
        factors = {
            'readability': self._calculate_readability(content),
            'structure': self._analyze_structure(content),
            'engagement': self._predict_engagement(content),
            'originality': self._check_originality(content)
        }

        weights = {
            'readability': 0.3,
            'structure': 0.2,
            'engagement': 0.3,
            'originality': 0.2
        }

        quality_score = sum(score * weights[factor] for factor, score in factors.items())
        return min(quality_score, 1.0)

    def _determine_category(self, content: str) -> str:
        """Determine content category using TF-IDF and classification"""
        categories = {
            "technology": ["tech", "software", "digital", "ai", "innovation"],
            "business": ["business", "strategy", "marketing", "finance"],
            "lifestyle": ["lifestyle", "health", "wellness", "travel"],
            "education": ["education", "learning", "study", "academic"]
        }

        content_lower = content.lower()
        category_scores = {
            category: sum(1 for keyword in keywords if keyword in content_lower)
            for category, keywords in categories.items()
        }

        max_category = max(category_scores.items(), key=lambda x: x[1])
        return max_category[0] if max_category[1] > 0 else "general"

    def _detect_emotional_content(self, content: str) -> float:
        """Detect emotional resonance in content"""
        emotional_words = {
            'high': ['amazing', 'incredible', 'awesome', 'fantastic'],
            'medium': ['good', 'great', 'nice', 'cool'],
            'low': ['okay', 'fine', 'normal', 'average']
        }

        content_lower = content.lower()
        scores = {
            'high': sum(word in content_lower for word in emotional_words['high']) * 1.0,
            'medium': sum(word in content_lower for word in emotional_words['medium']) * 0.6,
            'low': sum(word in content_lower for word in emotional_words['low']) * 0.3
        }

        total_score = sum(scores.values())
        max_possible = len(content.split()) / 20  # Assume 1 emotional word per 20 words is optimal

        return min(total_score / max_possible, 1.0) if max_possible > 0 else 0.0

    def _calculate_readability(self, content: str) -> float:
        """Calculate content readability score"""
        words = content.split()
        sentences = content.split('.')

        if not sentences or not words:
            return 0.0

        avg_words_per_sentence = len(words) / len(sentences)
        avg_word_length = sum(len(word) for word in words) / len(words)

        # Simplified readability score
        readability = 1.0 - (
            (avg_words_per_sentence - 15) / 30 +  # Optimal sentence length ~15 words
            (avg_word_length - 5) / 10            # Optimal word length ~5 characters
        ) / 2

        return max(min(readability, 1.0), 0.0)

    def _analyze_structure(self, content: str) -> float:
        """Analyze content structure quality"""
        paragraphs = content.split('\n\n')
        if not paragraphs:
            return 0.0

        # Check for good structure: presence of an introduction and conclusion and balanced paragraph lengths
        has_intro = len(paragraphs[0].split()) >= 20
        has_conclusion = len(paragraphs[-1].split()) >= 20
        avg_para_length = sum(len(p.split()) for p in paragraphs) / len(paragraphs)

        structure_score = (
            0.3 * has_intro +
            0.3 * has_conclusion +
            0.4 * (1.0 - abs(avg_para_length - 75) / 75)  # Optimal paragraph ~75 words
        )

        return max(min(structure_score, 1.0), 0.0)

    def _predict_engagement(self, content: str) -> float:
        """Predict potential engagement level"""
        features = {
            'has_question': 1 if '?' in content else 0,
            'has_numbers': 1 if any(c.isdigit() for c in content) else 0,
            'has_quotes': 1 if ('"' in content or "'" in content) else 0,
            'has_lists': 1 if any(line.strip().startswith(('-', '*', '1.')) for line in content.split('\n')) else 0,
            'has_call_to_action': 1 if any(cta in content.lower() for cta in ['follow', 'share', 'comment', 'like']) else 0
        }
        engagement_score = np.mean(list(features.values()))
        return min(engagement_score, 1.0)

    def _check_originality(self, content: str) -> float:
        """Check for originality by comparing with cached content similarity using cosine similarity."""
        if not self.content_cache:
            return 1.0  # No previous content to compare with
        try:
            new_vector = self.vectorizer.transform([content])
        except Exception as e:
            logger.error(f"Vectorization error: {e}")
            return 0.5

        similarities = []
        for cached_content in self.content_cache.values():
            try:
                cached_vector = self.vectorizer.transform([cached_content])
                # Compute dot product (assuming normalized vectors, this approximates cosine similarity)
                similarity = (new_vector * cached_vector.T).A[0][0]
                similarities.append(similarity)
            except Exception as e:
                logger.error(f"Error computing similarity: {e}")

        max_similarity = max(similarities) if similarities else 0
        originality_score = 1.0 - max_similarity  # Lower similarity means higher originality
        return max(min(originality_score, 1.0), 0.0)

    def _calculate_shareability(self, content: str) -> float:
        """Calculate shareability based on content factors"""
        score = 0.0
        if '?' in content:
            score += 0.3
        if any(cta in content.lower() for cta in ['share', 'retweet']):
            score += 0.3
        if any(line.strip().startswith(('-', '*', '1.')) for line in content.split('\n')):
            score += 0.2
        return min(score, 1.0)

    def _calculate_uniqueness(self, content: str) -> float:
        """Calculate uniqueness of content using the originality check"""
        return self._check_originality(content)

    def _check_timeliness(self, content: str) -> float:
        """Check for timeliness of content based on current year mention"""
        current_year = str(datetime.now().year)
        return 1.0 if current_year in content else 0.5

    async def store_content_item(self, content_item: ContentItem) -> None:
        """Store the content item in MongoDB"""
        try:
            client = AsyncIOMotorClient('mongodb://localhost:27017')
            db = client.contentflow
            collection = db.content_items
            await collection.insert_one(content_item.dict())
            logger.info(f"Stored content item with id: {content_item.id}")
        except Exception as e:
            logger.error(f"Error storing content item: {e}")
            raise e
