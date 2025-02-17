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
import re #Import the regular expression module

# Hardcode the LLM choice here:
llm_choice = "openai"  # Or "gemini", whichever you want as the default

# Instantiate the models via LLMSetup
# Only initialize the *selected* LLM, not both.
selected_llm = initialize_model(llm_choice)


# LLM configuration based on user's choice
if llm_choice == "openai":
    # OpenAI API setup
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    if not OPENAI_API_KEY:
        raise ValueError("Please set the OPENAI_API_KEY environment variable.")
    provider = "openai/gpt-4o-mini"  # Or your preferred model
    api_token = OPENAI_API_KEY
    OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
elif llm_choice == "gemini":  # NOT WORKING AT THE MOMENT!!!
    # Gemini Setup
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    if not GEMINI_API_KEY:
        raise ValueError("Please set the GEMINI_API_KEY environment variable.")
    genai.configure(api_key=GEMINI_API_KEY)
    provider = "gemini"  # This needs to match initialize_model
    api_token = GEMINI_API_KEY
    # gemini_model = genai.GenerativeModel("models/gemini-2.0-flash-thinking-exp-01-21") #Not needed here.
    # the initialize_model does this.
else:  # Important to add to avoid errors later
    raise ValueError("Invalid LLM Choice")

print("Setup complete.")

# Setup Supabase
url: str = os.environ.get("SUPABASE_URL")
print(f"MY URL is {url}")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

# Define JSON schema
class NewsItem(BaseModel):
    uniqueName: str = Field(
        ...,
        alias="id",
        description="Unique ID/use the headline and convert to lowercase with hyphens",
    )
    source: str = Field(..., description="Website domain or brand name")
    headline: str = Field(..., description="Extracted headline text")
    href: str = Field(..., description="Relative URL (href) from the anchor tag")
    url: str = Field(..., description="Full URL of the news item")
    publishedAt: str = Field(
        ..., alias="published_at", description="Publication date inन्तिथी-MM-DD format"
    )
    isProcessed: bool = Field(
        False, description="Flag indicating if the item has been processed"
    )


def clean_url_for_extraction(url: str) -> str:
    """Clean URL by removing non-printable characters and properly encoding."""
    if not url:
        return url
    
    # Remove all non-printable characters
    url = ''.join(char for char in url if ord(char) >= 32)
    
    # Normalize spaces and remove unwanted characters
    url = url.strip().replace('\n', '').replace('\r', '').replace(' ', '-')
    
    # Encode URL properly while preserving structure
    try:
        parts = urllib.parse.urlparse(url)
        path = urllib.parse.quote(parts.path)
        query = urllib.parse.quote_plus(parts.query, safe='=&')
        
        # Reconstruct the URL
        clean_url = urllib.parse.urlunparse((
            parts.scheme,
            parts.netloc,
            path,
            parts.params,
            query,
            parts.fragment
        ))
        return clean_url
    except Exception:
        # If URL parsing fails, just return the basic cleaned URL
        return url


# Define the scraper function
async def scrape_sports_news(
    url: str,
    base_url: str,
    schema: Type[BaseModel] = NewsItem,
    max_items: int = 10,
    time_period: str = "last 48 hours",
):
    """Reusable sports news scraper for any website"""

    # 2. Dynamic instruction with URL handling
    instruction = f"""
    Extract sports news articles from {url} with these rules:
    1. Extract ONLY the HREF attribute from anchor tags for the link field
    2. DO NOT prepend any base URL to the href field
    3. Source should be the website's domain (e.g. "nfl.com")
    4. Dates older than {time_period} should be excluded
    5. Create IDs from headlines (lowercase, hyphens, no special chars)
    6. Return max {max_items} most recent items
    """

    # 3. Configure extraction strategy
    strategy = LLMExtractionStrategy(
        provider=provider,
        api_token=api_token,
        schema=schema.schema_json(),
        extraction_type="schemas",
        instruction=instruction,
    )
    print(f"provider: {provider}")

    async with AsyncWebCrawler(verbose=True) as crawler:
        result = await crawler.arun(
            url=url,
            word_count_threshold=1,
            extraction_strategy=strategy,
            cache_mode=CacheMode.DISABLED,
        )
    # --- Crucial Change: Explicitly handle encoding ---
    # Decode using UTF-8, handling potential errors
    try:
        decoded_content = result.extracted_content.encode('latin-1', 'replace').decode('utf-8', 'replace')
    except Exception as e:
        print(f"Decoding error: {e}")
        decoded_content = result.extracted_content # Fallback to original if decoding fails

    # --- Crucial Change: Clean the extracted data ---
    extracted_data = json.loads(decoded_content)  # Use decoded content
    cleaned_data = []
    for item in extracted_data:
        # Clean the URL with enhanced cleaning:
        item["url"] = clean_url_for_extraction(item["url"])

        # Clean ID:
        item["id"] = re.sub(r'[^\w\-]', '', item["id"].lower().replace(" ", "-"))
        cleaned_data.append(item)
    return cleaned_data

async def get_all_news_items():
    websites = [
        {
            "name": "bleacherreport",
            "url": "https://www.bleacherreport.com/nfl",
            "base_url": "https://www.bleacherreport.com",
            "execute": False,
        },
        {
            "name": "nytimes",
            "url": "https://www.nytimes.com/athletic/nfl/",
            "base_url": "https://www.nytimes.com",
            "execute": False,
        },
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