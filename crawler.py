import asyncio
import logging
from typing import Optional
from playwright.async_api import async_playwright
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, BrowserConfig
from crawl4ai.extraction_strategy import LLMExtractionStrategy
from crawl4ai.content_filter_strategy import PruningContentFilter
from supabase import create_client
from models import DIYProject

# Configure logging to include timestamps and log level
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class DIYCrawler:
    def __init__(self, supabase_url: str, supabase_key: str, api_key: str):
        # Initialize Supabase client and store API key
        self.supabase = create_client(supabase_url, supabase_key)
        self.api_key = api_key

        # Configure headless browser settings using Playwright-compatible settings
        self.browser_config = BrowserConfig(
            headless=True,
            browser_type="chromium"
        )

        # Base crawler configuration with content filtering
        self.crawler_config = CrawlerRunConfig(
            excluded_tags=['nav', 'footer', 'aside'],
            remove_overlay_elements=True,
            content_filter=PruningContentFilter(
                threshold=0.4,
                min_word_threshold=50
            )
        )

    @staticmethod
    async def on_page_context_created(page, context, **kwargs):
        """
        Hook function to set the viewport size once the page context is created.
        """
        await page.set_viewport_size({"width": 1280, "height": 800})

    def create_extraction_config(self) -> CrawlerRunConfig:
        """
        Create and return an extraction configuration with optimized settings
        to reduce payload size and avoid rate limiting issues.
        """
        return CrawlerRunConfig(
            excluded_tags=self.crawler_config.excluded_tags,
            remove_overlay_elements=self.crawler_config.remove_overlay_elements,
            content_filter=self.crawler_config.content_filter,
            extraction_strategy=LLMExtractionStrategy(
                provider="groq/llama3-8b-8192",
                api_token=self.api_key,
                schema=DIYProject.model_json_schema(),  # Use the model's JSON schema
                extraction_type="schema",
                instruction="""
                    Extract DIY project details including:
                    - Materials list with quantities
                    - Step-by-step instructions
                    - Difficulty level
                    - Category and tags
                    Format for makers and hobbyists.
                """,
                chunk_token_threshold=800,   # Reduced chunk size to prevent 413 errors
                overlap_rate=0.05,           # Reduced overlap to lower redundancy
                apply_chunking=True,
                extra_args={
                    "temperature": 0.1,
                    "max_tokens": 150        # Lower token output size to reduce payload
                }
            )
        )

    def process_result(self, result, url: str) -> Optional[DIYProject]:
        """
        Process the API result with robust error handling.
        Checks for NoneType responses and unexpected data structures.
        """
        if not result or not hasattr(result, "extracted_content") or not result.extracted_content:
            logging.error(f"Invalid or empty response from API for {url}, skipping...")
            return None

        extracted_content = result.extracted_content

        # Handle the case where the API returns a list instead of a dictionary
        if isinstance(extracted_content, list):
            if extracted_content:
                logging.warning(f"Unexpected list response from API for {url}, taking the first element.")
                extracted_content = extracted_content[0]
            else:
                logging.error(f"Extracted content list is empty for {url}, skipping...")
                return None

        # Ensure the content is in the expected dictionary format
        if not isinstance(extracted_content, dict):
            logging.error(f"Extracted content is not a dictionary for {url}, skipping...")
            return None

        try:
            # Validate and construct a DIYProject model instance
            return DIYProject.model_validate_json(extracted_content)
        except Exception as e:
            logging.error(f"Failed to validate DIYProject model for {url}: {str(e)}")
            return None

    async def extract_project(self, url: str) -> Optional[DIYProject]:
        """
        Extract DIY project information from the provided URL.
        Implements retries with exponential backoff to handle rate limiting and transient errors.
        """
        logging.info(f"Processing URL: {url}")

        async with AsyncWebCrawler(config=self.browser_config, verbose=True) as crawler:
            # Set the viewport hook for newly created pages
            crawler.crawler_strategy.set_hook("on_page_context_created", self.on_page_context_created)

            # Use the optimized extraction configuration
            extraction_config = self.create_extraction_config()
            max_attempts = 5

            for attempt in range(max_attempts):
                try:
                    result = await crawler.arun(url=url, config=extraction_config)

                    # Handle rate limit errors with a capped exponential backoff
                    if getattr(result, "error_message", "") and "rate_limit_exceeded" in result.error_message:
                        wait_time = min((attempt + 1) * 5, 30)  # Wait times: 5s, 10s, ... capped at 30s
                        logging.warning(f"Rate limit exceeded for {url}, retrying in {wait_time} seconds...")
                        await asyncio.sleep(wait_time)
                        continue

                    # If the result is missing or indicates a failure, log and exit the loop
                    if not result or not getattr(result, "success", False):
                        logging.error(f"API returned invalid response for {url}, skipping...")
                        return None

                    # If a list is returned, pick the first element
                    if isinstance(result, list) and result:
                        logging.warning(f"API returned a list for {url}, using the first element.")
                        result = result[0]

                    # Process the result using the helper method
                    project = self.process_result(result, url)
                    if project is None:
                        logging.error(f"Failed to process project data for {url}.")
                    return project

                except Exception as e:
                    logging.error(f"Attempt {attempt + 1} failed for {url}: {str(e)}")
                    if attempt == max_attempts - 1:
                        raise  # Raise the exception on the final attempt
                    backoff_time = min(2 ** attempt, 30)  # Exponential backoff (2^attempt, capped at 30 seconds)
                    logging.info(f"Retrying in {backoff_time} seconds...")
                    await asyncio.sleep(backoff_time)

        # If all attempts fail, return None
        return None
