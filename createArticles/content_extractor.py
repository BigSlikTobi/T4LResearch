import httpx
from urllib.parse import urlparse
from crawl4ai import AsyncWebCrawler, CacheMode, LLMExtractionStrategy
import json
import yaml
import os

def load_prompts():
    with open(os.path.join(os.path.dirname(__file__), "prompts.yaml"), "r") as f:
        return yaml.safe_load(f)

class ContentExtractor:
    def __init__(self, model_name: str, api_key: str):
        self.model_name = model_name
        self.api_key = api_key
        self.prompts = load_prompts()

    async def is_valid_url(self, url: str) -> bool:
        """
        Checks if the URL is well-formed and reachable using async httpx.
        """
        headers = {
            "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Safari/537.36")
        }
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            return False
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.head(url, headers=headers, timeout=10.0)
                if response.status_code == 200:
                    return True
                # Fallback to GET if HEAD fails
                response = await client.get(url, headers=headers, timeout=10.0)
                return response.status_code == 200
            except Exception as e:
                print(f"URL validation exception for {url}: {e}")
                return False

    async def extract_article_content(self, url: str) -> str:
        """
        Extracts the core content from the provided URL using Crawl4AI.
        """
        async with AsyncWebCrawler(verbose=False) as crawler:
            strategy = LLMExtractionStrategy(
                provider=self.model_name,
                verbose=True,
                api_token=self.api_key,
                instructions=self.prompts["content_extraction_prompt"],
                output_format="json",
            )
            result = await crawler.arun(
                url=url,
                extraction_strategy=strategy,
                max_pages=1,
                cache_mode=CacheMode.WRITE_ONLY,
            )
            raw_json = result.extracted_content
            try:
                data = json.loads(raw_json)
            except Exception as e:
                print(f"Error parsing extraction result from {url}: {e}")
                return ""
            
            texts = []
            if isinstance(data, list):
                for block in data:
                    text = block.get("content", "")
                    if isinstance(text, list):
                        texts.append(" ".join(text))
                    elif isinstance(text, str):
                        texts.append(text)
            else:
                texts.append(str(data))
            return "\n".join(texts)