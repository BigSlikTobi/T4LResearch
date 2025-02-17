#TODO: Make Gemin work

import os
import json
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

# Instantiate the models via LLMSetup
llms = initialize_model("both")
while True:
    llm_choice = input("Select LLM (gemini/openai): ").lower()
    if llm_choice in llms:
        selected_llm = llms[llm_choice]
        break
    else:
        print("Invalid LLM choice. Please select 'gemini' or 'openai'.")

# LLM configuration based on user's choice
if llm_choice == "openai":
    # OpenAI API setup
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    if not OPENAI_API_KEY:
        raise ValueError("Please set the OPENAI_API_KEY environment variable.")
    provider = "openai/gpt-4o-mini"  # Or your preferred model
    api_token = OPENAI_API_KEY
    OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
elif llm_choice == "gemini": #NOT WORKING AT THE MOMENT!!!
    # Gemini Setup
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    if not GEMINI_API_KEY:
        raise ValueError("Please set the GEMINI_API_KEY environment variable.")
    genai.configure(api_key=GEMINI_API_KEY)
    provider = "gemini"
    api_token = GEMINI_API_KEY
    gemini_model = genai.GenerativeModel("models/gemini-2.0-flash-thinking-exp-01-21")

print("Setup complete.")

# Setup Supabase
url: str = os.environ.get("SUPABASE_URL")
print(f"MY URL is {url}")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

# Define JSON schema
class NewsItem(BaseModel):
    uniqueName: str = Field(..., alias="id", description="Unique ID/use the headline and convert to lowercase with hyphens")
    source: str = Field(..., description="Website domain or brand name")
    headline: str = Field(..., description="Extracted headline text")
    href: str = Field(..., description="Relative URL (href) from the anchor tag")
    url: str = Field(..., description="Full URL of the news item")
    publishedAt: str = Field(..., alias="published_at", description="Publication date in YYYY-MM-DD format")
    isProcessed: bool = Field(False, description="Flag indicating if the item has been processed")

# Define the scraper function
async def scrape_sports_news(
url: str,
    base_url: str,
    schema: Type[BaseModel] = NewsItem,
    max_items: int = 10,
    time_period: str = "last 48 hours"
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
    print(result.extracted_content)
    return json.loads(result.extracted_content)

# New function to obtain and combine news items from each site
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
