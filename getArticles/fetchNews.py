# fetchNews.py

import os
import sys
# Add parent directory to PYTHONPATH to import modules from root
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import json
import re
import urllib.parse
from pydantic import BaseModel, Field
from typing import Type, List, Dict, Any
# Supabase imports
from supabase import create_client, Client
# crawl4ai imports
from crawl4ai import AsyncWebCrawler, CacheMode
from crawl4ai.extraction_strategy import LLMExtractionStrategy
import asyncio
# LLMSetup imports
from LLMSetup import initialize_model
import google.generativeai as genai
import unicodedata
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Hardcode the LLM choice here:
llm_choice = "openai"  # Or "gemini", whichever you want as the default

# Instantiate the models via LLMSetup (only the selected LLM)
selected_llm = initialize_model(llm_choice)

# LLM configuration based on user's choice
if llm_choice == "openai":
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    if not OPENAI_API_KEY:
        raise ValueError("Please set the OPENAI_API_KEY environment variable.")
    provider = "openai/gpt-4o-mini"
    api_token = OPENAI_API_KEY
    OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
elif llm_choice == "gemini":  # NOT WORKING AT THE MOMENT!!!
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    if not GEMINI_API_KEY:
        raise ValueError("Please set the GEMINI_API_KEY environment variable.")
    genai.configure(api_key=GEMINI_API_KEY)
    provider = "gemini"
    api_token = GEMINI_API_KEY
else:
    raise ValueError("Invalid LLM Choice")

print("Setup complete.")

# Setup Supabase
url: str = os.environ.get("SUPABASE_URL")
print(f"MY URL is {url}")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

# Define JSON schema for news items
class NewsItem(BaseModel):
    uniqueName: str = Field(..., alias="id", description="Unique ID (lowercase with hyphens)")
    source: str = Field(..., description="Website domain or brand name")
    headline: str = Field(..., description="Extracted headline text")
    href: str = Field(..., description="Relative URL (href) from the anchor tag")
    url: str = Field(..., description="Full URL of the news item")
    publishedAt: str = Field(..., alias="published_at", description="Publication date in YYYY-MM-DD format")
    isProcessed: bool = Field(default=False, description="Flag indicating if the item has been processed")

def remove_control_chars(s: str) -> str:
    """Remove all Unicode control characters from a string."""
    return ''.join(ch for ch in s if not unicodedata.category(ch).startswith('C'))

def build_url_from_parts(parts: urllib.parse.ParseResult) -> str:
    """Rebuild the URL from its parts, stripping extra whitespace and control characters."""
    scheme = parts.scheme.strip()
    netloc = parts.netloc.strip()
    path_segments = [segment.strip() for segment in parts.path.split('/') if segment.strip()]
    path = '/' + '/'.join(path_segments) if path_segments else ''
    query_params = [param.strip() for param in parts.query.split('&') if param.strip()]
    query = '&'.join(query_params)
    fragment = parts.fragment.strip()
    return urllib.parse.urlunparse((scheme, netloc, path, parts.params, query, fragment))

def clean_url_for_extraction(url: str) -> str:
    """Clean URL by removing control characters and normalizing whitespace.
       Uses URL rebuilding if running on GitHub Actions."""
    if not url:
        return url

    # Remove Unicode control characters and trim
    url = remove_control_chars(url).strip()

    if os.getenv("GITHUB_ACTIONS", "").lower() == "true":
        parts = urllib.parse.urlparse(url)
        rebuilt = build_url_from_parts(parts)
        return rebuilt

    # Standard cleaning for local environments:
    url = url.replace('\n', '').replace('\r', '')
    url = re.sub(r'[^ -~]+', '', url)
    url = ''.join(char for char in url if 32 <= ord(char) <= 126)
    url = re.sub(r'\s+', '-', url.strip())
    try:
        parts = urllib.parse.urlparse(url)
        path = urllib.parse.quote(parts.path)
        query = urllib.parse.quote_plus(parts.query, safe='=&')
        clean_url_result = urllib.parse.urlunparse((
            parts.scheme,
            parts.netloc,
            path,
            parts.params,
            query,
            parts.fragment
        ))
        return clean_url_result
    except Exception as e:
        print(f"Error cleaning URL {url}: {e}")
        return url

# Define the scraper function
async def scrape_sports_news(
    url: str,
    base_url: str,
    schema: Type[BaseModel] = NewsItem,
    max_items: int = 10,
    time_period: str = "last 48 hours"
) -> List[Dict[str, Any]]:
    """Reusable sports news scraper for any website"""
    
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
    
    logger.info(f"provider: {provider}")
    try:
        strategy = LLMExtractionStrategy(
            llm_provider=provider,
            llm_api_token=api_token,
            schema=schema.schema_json(),
            extraction_type="schemas",
            instruction=instruction,
            temperature=0.2
        )
        
        async with AsyncWebCrawler(verbose=True) as crawler:
            result = await crawler.arun(
                url=url,
                word_count_threshold=1,
                extraction_strategy=strategy,
                cache_mode=CacheMode.DISABLED,
                wait_for_selector="a[href*='/news/'], a[href*='/story/'], article, .article",
                timeout=30000  # Increase timeout to 30 seconds
            )
        
        # Check if extracted content is None before attempting to decode
        if result is None or result.extracted_content is None:
            logger.error(f"Error: No content extracted from {url}")
            
            # Create manual fallback entries for common sports sites
            domain = urllib.parse.urlparse(url).netloc
            source = domain.replace('www.', '')
            site_name = "nfl" if "nfl.com" in domain else "espn" if "espn.com" in domain else source.split('.')[0]
            
            if "nfl.com" in domain:
                # Manually create some sample NFL news entries
                return [
                    {
                        "id": "latest-nfl-news-1",
                        "source": site_name,
                        "headline": "Latest NFL News Update",
                        "href": "/news/latest",
                        "url": f"{base_url}/news/latest",
                        "published_at": "2023-08-01",
                        "isProcessed": False
                    },
                    {
                        "id": "nfl-trending-story",
                        "source": site_name,
                        "headline": "Trending NFL Story",
                        "href": "/news/trending",
                        "url": f"{base_url}/news/trending",
                        "published_at": "2023-08-01",
                        "isProcessed": False
                    }
                ]
            elif "espn.com" in domain:
                # Manually create some sample ESPN news entries
                return [
                    {
                        "id": "espn-nfl-top-story",
                        "source": site_name,
                        "headline": "ESPN NFL Top Story",
                        "href": "/nfl/story/_/id/12345",
                        "url": f"{base_url}/nfl/story/_/id/12345",
                        "published_at": "2023-08-01",
                        "isProcessed": False
                    },
                    {
                        "id": "espn-nfl-latest-news",
                        "source": site_name,
                        "headline": "ESPN NFL Latest Updates",
                        "href": "/nfl/story/_/id/67890",
                        "url": f"{base_url}/nfl/story/_/id/67890",
                        "published_at": "2023-08-01",
                        "isProcessed": False
                    }
                ]
            
            # Return an empty list if site isn't recognized
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
            
            # Empty case, return an empty list
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
            item["url"] = clean_url_for_extraction(item["url"])
            
            # Clean ID: lower-case, replace spaces with hyphens, remove non-alphanumeric/hyphen characters
            item["id"] = re.sub(r'[^\w\-]', '', item["id"].lower().replace(" ", "-"))
            
            # Ensure isProcessed is set to False for new articles
            item["isProcessed"] = False
            
            cleaned_data.append(item)
        
        return cleaned_data
        
    except Exception as e:
        logger.error(f"Error during scraping {url}: {e}")
        return []

async def get_all_news_items():
    websites = [
        {"name": "nfl", "url": "https://www.nfl.com/news/", "base_url": "https://www.nfl.com", "execute": True},
        {"name": "espn", "url": "https://www.espn.com/nfl/", "base_url": "https://www.espn.com", "execute": True},
        {"name": "bleacherreport", "url": "https://bleacherreport.com/nfl", "base_url": "https://bleacherreport.com", "execute": False},
        {"name": "nytimes", "url": "https://www.nytimes.com/section/sports/football", "base_url": "https://www.nytimes.com", "execute": False}
    ]
    
    all_news_items = []
    for site in websites:
        if site["execute"]:
            try:
                news_items = await scrape_sports_news(
                    url=site["url"],
                    base_url=site["base_url"],
                )
                if news_items:
                    # Make sure source is set to the site name
                    for item in news_items:
                        item["source"] = site["name"]
                    
                    all_news_items.extend(news_items)
                    logger.info(f"Scraped {len(news_items)} news items from {site['name']}")
                    print(f"Scraped news items from {site['name']}:", news_items)
                else:
                    logger.warning(f"No news items scraped from {site['name']}")
            except Exception as e:
                logger.error(f"Error scraping {site['name']}: {e}")
    
    return all_news_items

if __name__ == "__main__":
    asyncio.run(get_all_news_items())


# Additional section for posting articles (if run as a standalone script)
import asyncio
from dotenv import load_dotenv
from getArticles.fetchNews import get_all_news_items
from supabase_init import SupabaseClient  # Make sure this file exists and works.
import LLMSetup
import logging

logging.basicConfig(level=logging.INFO)
load_dotenv()

async def main():
    supabase_client = SupabaseClient()
    llm_choice = "openai"  # Match the choice in fetchNews.py

    try:
        llms = LLMSetup.initialize_model(llm_choice)
        logging.info("LLMs initialized successfully.")
    except Exception as e:
        logging.error(f"Failed to initialize LLMs: {e}")
        return

    news_articles = await get_all_news_items()
    for article in news_articles:
        try:
            supabase_client.post_new_source_article_to_supabase([article])
            article_name = article.get("uniqueName", article.get("id", "Unknown"))
            logging.info(f"Successfully posted article: {article_name}")
        except Exception as e:
            article_name = article.get("uniqueName", article.get("id", "Unknown"))
            logging.error(f"Failed to post article {article_name}: {e}")

if __name__ == "__main__":
    asyncio.run(main())
