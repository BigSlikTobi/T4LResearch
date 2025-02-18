# fetchNews.py

import os
import sys
# Add parent directory to PYTHONPATH to import modules from root
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import json
import re
import urllib.parse
from pydantic import BaseModel, Field
from typing import Type
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
    isProcessed: bool = Field(False, description="Flag indicating if the item has been processed")

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
):
    """Reusable sports news scraper for any website"""

    instruction = f"""
    Extract sports news articles from {url} with these rules:
    1. Extract ONLY the HREF attribute from anchor tags for the link field
    2. DO NOT prepend any base URL to the href field
    3. Source should be the website's domain (e.g. "nfl.com")
    4. Exclude dates older than {time_period}
    5. Create IDs from headlines (lowercase, hyphens, no special chars)
    6. Return max {max_items} most recent items
    """

    strategy = LLMExtractionStrategy(
        provider=provider,
        api_token=api_token,
        schema=schema.schema_json(),
        extraction_type="schemas",
        instruction=instruction
    )
    print(f"provider: {provider}")

    async with AsyncWebCrawler(verbose=True) as crawler:
        result = await crawler.arun(
            url=url,
            word_count_threshold=1,
            extraction_strategy=strategy,
            cache_mode=CacheMode.DISABLED
        )
    try:
        decoded_content = result.extracted_content.encode('latin-1', 'replace').decode('utf-8', 'replace')
    except Exception as e:
        print(f"Decoding error: {e}")
        decoded_content = result.extracted_content

    extracted_data = json.loads(decoded_content)
    cleaned_data = []
    for item in extracted_data:
        # Clean URL for extraction using our enhanced logic:
        item["url"] = clean_url_for_extraction(item["url"])
        # Clean ID: lower-case, replace spaces with hyphens, remove non-alphanumeric/hyphen characters
        item["id"] = re.sub(r'[^\w\-]', '', item["id"].lower().replace(" ", "-"))
        cleaned_data.append(item)
    return cleaned_data

async def get_all_news_items():
    websites = [
        {"name": "nfl", "url": "https://www.nfl.com/news/", "base_url": "https://www.nfl.com", "execute": True},
        {"name": "espn", "url": "https://www.espn.com/nfl/", "base_url": "https://www.espn.com", "execute": True},
        {"name": "bleacherreport", "url": "https://www.bleacherreport.com/nfl", "base_url": "https://www.bleacherreport.com", "execute": False},
        {"name": "nytimes", "url": "https://www.nytimes.com/athletic/nfl/", "base_url": "https://www.nytimes.com", "execute": False}
    ]
    all_news_items = []
    for site in websites:
        if site["execute"]:
            news_items = await scrape_sports_news(
                url=site["url"],
                base_url=site["base_url"],
            )
            all_news_items.extend(news_items)
            print(f"Scraped news items from {site['name']}:", news_items)
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
