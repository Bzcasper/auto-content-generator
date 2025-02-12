# ContentFlow: Automated Web Content Pipeline
# main.py

import os
import json
import asyncio
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, HttpUrl
from PIL import Image
import aiohttp
from crawl4ai import AsyncWebCrawler
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from supabase import create_client, Client

class ImageAsset(BaseModel):
    """Represents a processed image asset"""
    original_url: HttpUrl
    local_path: Path
    alt_text: Optional[str] = None
    size_bytes: int = 0
    width: int = 800  # Default width for resized images
    height: int = 600  # Default height for resized images

class ContentItem(BaseModel):
    """Structured content for processing"""
    url: HttpUrl
    title: str
    content: str
    summary: Optional[str]
    images: List[ImageAsset] = []
    tags: List[str] = []
    created_at: datetime = Field(default_factory=datetime.now)

class ContentProcessor:
    def __init__(self, config_path: str):
        self.config = self._load_config(config_path)
        self.crawler = AsyncWebCrawler(verbose=True)
        self.supabase = create_client(
            self.config["supabase"]["url"],
            self.config["supabase"]["api_key"]
        )
        self.setup_directories()

    def _load_config(self, path: str) -> dict:
        with open(path) as f:
            return json.load(f)

    def setup_directories(self):
        """Create necessary directories in Obsidian vault"""
        vault_path = Path(self.config["obsidian"]["vault_path"])
        self.content_dir = vault_path / "Content"
        self.images_dir = vault_path / "Assets" / "Images"
        
        for dir in [self.content_dir, self.images_dir]:
            dir.mkdir(parents=True, exist_ok=True)

    async def process_url(self, url: str) -> Optional[ContentItem]:
        """Process a single URL and extract content"""
        try:
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

            result = await self.crawler.arun(url=url, config=config)
            
            if not result.success:
                return None

            # Process images
            images = []
            for img in result.media.get('images', []):
                if processed_img := await self.process_image(img['src'], img.get('alt')):
                    images.append(processed_img)

            return ContentItem(
                url=url,
                title=result.metadata.get('title', 'Untitled'),
                content=result.markdown_v2.fit_markdown,
                summary=result.metadata.get('description', '')[:500],
                images=images,
                tags=self._extract_tags(result)
            )

        except Exception as e:
            print(f"Error processing {url}: {str(e)}")
            return None

    async def process_image(self, url: str, alt_text: Optional[str] = None) -> Optional[ImageAsset]:
        """Download and process an image"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.read()
                        filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash(url)}.webp"
                        filepath = self.images_dir / filename

                        # Process image with Pillow
                        img = Image.open(BytesIO(data))
                        img = img.resize((800, 600), Image.LANCZOS)
                        img.save(filepath, 'WEBP', quality=85)

                        return ImageAsset(
                            original_url=url,
                            local_path=filepath,
                            alt_text=alt_text,
                            size_bytes=len(data)
                        )
            return None
        except Exception as e:
            print(f"Error processing image {url}: {str(e)}")
            return None

    def _extract_tags(self, result: Any) -> List[str]:
        """Extract tags from content metadata"""
        tags = set()
        if result.metadata.get('keywords'):
            tags.update(k.strip().lower() for k in result.metadata['keywords'].split(','))
        return list(tags)

    def save_to_obsidian(self, item: ContentItem):
        """Save content to Obsidian vault"""
        filename = f"{datetime.now().strftime('%Y%m%d')}_{self._sanitize_filename(item.title)}.md"
        filepath = self.content_dir / filename

        # Build markdown content
        content = f"""---
title: {item.title}
url: {item.url}
date: {item.created_at.strftime('%Y-%m-%d')}
tags: {', '.join(item.tags)}
---

# {item.title}

{item.summary if item.summary else ''}

## Content

{item.content}

## Images

"""
        # Add image references
        for img in item.images:
            rel_path = os.path.relpath(img.local_path, self.config["obsidian"]["vault_path"])
            content += f"\n![[{rel_path}]]\n"

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

    async def save_to_supabase(self, item: ContentItem):
        """Save content to Supabase"""
        try:
            data = {
                "url": str(item.url),
                "title": item.title,
                "content": item.content,
                "summary": item.summary,
                "images": [{"url": str(img.original_url), "path": str(img.local_path)} for img in item.images],
                "tags": item.tags,
                "created_at": item.created_at.isoformat()
            }
            
            result = self.supabase.table(self.config["supabase"]["table"]).insert(data).execute()
            return result
        except Exception as e:
            print(f"Error saving to Supabase: {str(e)}")
            return None

    @staticmethod
    def _sanitize_filename(filename: str) -> str:
        """Create safe filenames"""
        return "".join(c for c in filename if c.isalnum() or c in "._- ").rstrip()

async def main():
    # Load URLs
    with open("urls.json") as f:
        urls = json.load(f)["urls"]

    processor = ContentProcessor("config.json")
    
    for url in urls:
        print(f"\nProcessing: {url}")
        if content := await processor.process_url(url):
            processor.save_to_obsidian(content)
            await processor.save_to_supabase(content)
            print(f"Successfully processed {url}")
        else:
            print(f"Failed to process {url}")

if __name__ == "__main__":
    asyncio.run(main())
