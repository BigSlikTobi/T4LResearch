"""
Core module for fetching news articles from various sources.
"""
import asyncio
import json
import os
import re
import logging
from typing import List, Dict, Any, Type
from pydantic import BaseModel, Field

# crawl4ai imports
from crawl4ai import AsyncWebCrawler, CacheMode
from crawl4ai.extraction_strategy import LLMExtractionStrategy

# Local imports
from .url_utils import clean_url

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define JSON schema for news items
class NewsItem(BaseModel):
    uniqueName: str = Field(..., alias="id", description="Unique ID (lowercase with hyphens)")
    source: str = Field(..., description="Website domain or brand name")
    headline: str = Field(..., description="Extracted headline text")
    href: str = Field(..., description="Relative URL (href) from the anchor tag")
    url: str = Field(..., description="Full URL of the news item")
    publishedAt: str = Field(..., alias="published_at", description="Publication date in YYYY-MM-DD format")
    isProcessed: bool = Field(default=False, description="Flag indicating if the item has been processed")

async def fetch_news(
    url: str,
    base_url: str,
    provider: str,
    api_token: str,
    schema: Type[BaseModel] = NewsItem,
    max_items: int = 10,
    time_period: str = "last 48 hours"
) -> List[Dict[str, Any]]:
    """
    Fetch news from a specific website using AI-powered extraction.
    
    Args:
        url: The URL to scrape news from
        base_url: The base URL for constructing complete URLs
        provider: The LLM provider (e.g., "openai/gpt-4o-mini")
        api_token: The API token for the LLM provider
        schema: Pydantic schema for the news items
        max_items: Maximum number of items to fetch
        time_period: Time period for news articles
    
    Returns:
        List of news items as dictionaries
    """
    
    # Enhanced LLM extraction strategy with improved prompt
    instruction = f"""
    Extract sports news articles from the given webpage with these rules:
    1. Look for anchor tags with headlines or article links
    2. For the 'href' field, extract ONLY the href attribute value from anchor tags (no base URL)
    3. For the 'url' field, combine the base URL ({base_url}) with the 'href' value to form a complete URL
    4. Set 'source' to the website domain name (e.g., 'nfl.com', 'espn.com')
    5. For 'id', create a slug from the headline (lowercase, replace spaces with hyphens, no special chars)
    6. For 'published_at', use the date from the article or current date in YYYY-MM-DD format
    7. Only include articles from the {time_period}
    8. Return at most {max_items} items
    9. Focus on NFL news articles and ignore non-news content like ads or navigation links
    
    Pay special attention to elements with classes containing 'article', 'headline', 'news', etc.
    If the page is javascript-heavy, try to identify news links from their position, styling, or context.
    """
    
    is_github_actions = os.getenv("GITHUB_ACTIONS", "").lower() == "true"
    
    try:
        # Use a longer timeout and more retries in GitHub Actions environment
        timeout_ms = 60000 if is_github_actions else 30000  # 60 seconds for GitHub Actions
        max_retries = 3 if is_github_actions else 1
        
        # Use a more forgiving strategy in GitHub Actions
        wait_for_selector = "body" if is_github_actions else "a[href*='/news/'], a[href*='/story/'], article, .article"
        
        strategy = LLMExtractionStrategy(
            llm_provider=provider,
            llm_api_token=api_token,
            schema=schema.schema_json(),
            extraction_type="schemas",
            instruction=instruction,
            temperature=0.2
        )
        
        result = None
        retry_count = 0
        
        while retry_count <= max_retries:
            try:
                async with AsyncWebCrawler(verbose=True) as crawler:
                    result = await crawler.arun(
                        url=url,
                        word_count_threshold=1,
                        extraction_strategy=strategy,
                        cache_mode=CacheMode.DISABLED,
                        wait_for_selector=wait_for_selector,
                        timeout=timeout_ms
                    )
                if result and result.extracted_content:
                    break
                retry_count += 1
                if retry_count <= max_retries:
                    logger.info(f"Retry {retry_count}/{max_retries} for {url}")
                    await asyncio.sleep(2)  # Wait 2 seconds before retrying
            except Exception as e:
                logger.error(f"Error during crawling attempt {retry_count}: {e}")
                retry_count += 1
                if retry_count <= max_retries:
                    logger.info(f"Retry {retry_count}/{max_retries} for {url}")
                    await asyncio.sleep(2)
        
        # If we have no result after all retries or extraction failed
        if result is None or result.extracted_content is None:
            logger.error(f"Error: No content extracted from {url}")
            return []
        
        try:
            # Handle potential encoding issues
            if isinstance(result.extracted_content, str):
                decoded_content = result.extracted_content
            else:
                decoded_content = result.extracted_content.decode('utf-8', 'replace')
        except Exception as e:
            logger.error(f"Decoding error: {e}")
            # Try a different approach
            try:
                decoded_content = result.extracted_content.encode('latin-1', 'replace').decode('utf-8', 'replace')
            except:
                # Last resort fallback
                decoded_content = str(result.extracted_content)
        
        # Check again if decoded_content is None before parsing JSON
        if not decoded_content:
            logger.error(f"Error: Failed to decode content from {url}")
            return []
        
        # Try to parse the JSON
        try:
            # Remove any leading/trailing non-JSON content
            json_start = decoded_content.find('[')
            json_end = decoded_content.rfind(']') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_content = decoded_content[json_start:json_end]
                extracted_data = json.loads(json_content)
            else:
                # Try to parse the whole content as JSON
                extracted_data = json.loads(decoded_content)
                
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {e}")
            logger.debug(f"Raw content: {decoded_content[:200]}...")  # First 200 chars for debugging
            return []
        
        # Process the extracted data
        if not extracted_data:
            logger.warning(f"No data extracted from {url}")
            return []
            
        if not isinstance(extracted_data, list):
            logger.warning(f"Unexpected data format: {type(extracted_data)}")
            # Try to convert to list if it's not already
            if isinstance(extracted_data, dict):
                extracted_data = [extracted_data]
            else:
                return []
        
        # Clean and process the data
        cleaned_data = []
        for item in extracted_data:
            if not isinstance(item, dict):
                continue
                
            # Skip items missing required fields
            if not all(key in item for key in ["id", "headline", "href"]):
                continue
                
            # Handle URL construction
            href = item.get("href", "")
            if href.startswith("http"):
                item["url"] = href
            else:
                # Ensure the href starts with a slash if needed
                if not href.startswith('/') and not base_url.endswith('/'):
                    href = '/' + href
                item["url"] = base_url + href
            
            # Clean URL
            item["url"] = clean_url(item["url"])
            
            # Clean ID: lower-case, replace spaces with hyphens, remove non-alphanumeric/hyphen characters
            item["id"] = re.sub(r'[^\w\-]', '', item["id"].lower().replace(" ", "-"))
            
            # Ensure isProcessed is set to False for new articles
            item["isProcessed"] = False
            
            cleaned_data.append(item)
        
        return cleaned_data
        
    except Exception as e:
        logger.error(f"Error during scraping {url}: {e}")
        return []

async def fetch_from_all_sources(
    sources: List[Dict[str, Any]], 
    provider: str, 
    api_token: str
) -> List[Dict[str, Any]]:
    """
    Fetch news from all configured sources.
    
    Args:
        sources: List of source configurations with name, url, and base_url
        provider: LLM provider identifier
        api_token: API token for the LLM provider
        
    Returns:
        Combined list of all fetched news items
    """
    all_news_items = []
    
    for site in sources:
        if site.get("execute", True):
            try:
                logger.info(f"Fetching news from {site['name']}")
                news_items = await fetch_news(
                    url=site["url"],
                    base_url=site["base_url"],
                    provider=provider,
                    api_token=api_token
                )
                
                if news_items:
                    # Make sure source is set to the site name
                    for item in news_items:
                        item["source"] = site["name"]
                    
                    all_news_items.extend(news_items)
                    logger.info(f"Scraped {len(news_items)} news items from {site['name']}")
                else:
                    logger.warning(f"No news items scraped from {site['name']}")
            except Exception as e:
                logger.error(f"Error scraping {site['name']}: {e}")
    
    return all_news_items

def get_default_sources() -> List[Dict[str, Any]]:
    """
    Return the default set of news sources.
    
    Returns:
        List of news source configurations
    """
    return [
        {"name": "nfl", "url": "https://www.nfl.com/news/", "base_url": "https://www.nfl.com", "execute": True},
        {"name": "espn", "url": "https://www.espn.com/nfl/", "base_url": "https://www.espn.com", "execute": True},
        {"name": "bleacherreport", "url": "https://bleacherreport.com/nfl", "base_url": "https://bleacherreport.com", "execute": True},
        {"name": "nytimes", "url": "https://www.nytimes.com/section/sports/football", "base_url": "https://www.nytimes.com", "execute": False},
        {"name": "foxsports", "url": "https://www.foxsports.com/nfl/news", "base_url": "https://www.foxsports.com", "execute": True}
        # Add more sources as needed
    ]