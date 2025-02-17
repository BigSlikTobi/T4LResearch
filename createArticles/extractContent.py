import os
import json
import asyncio
from crawl4ai import AsyncWebCrawler, CacheMode
from crawl4ai.extraction_strategy import LLMExtractionStrategy
from fetchUnprocessedArticles import get_unprocessed_articles
from ..LLMSetup import init_openai, initialize_model

# Initialize OpenAI model
model_config = initialize_model("openai")
provider = model_config["model_name"]
api_token = model_config["model"]["api_key"]

async def extract_main_content(full_url: str) -> str:
    async with AsyncWebCrawler(verbose=False) as crawler:
        strategy = LLMExtractionStrategy(
            provider=provider,
            verbose=True,  # Set to True for debugging if needed.
            api_token=api_token,
            word_count_threshold=50,
            exclude_tags=["footer", "header", "nav", "aside", "script", "style","img"],
            exclude_external_links=True,
            instructions="""
                You are a content extractor. Extract the relevant text blocks
                and return them in JSON format as a list of objects,
                each with "tags" and "content".
                Only include the core article content.
            """,
            output_format="json",
        )
        result = await crawler.arun(
            url=full_url,
            extraction_strategy=strategy,
            max_pages=1,
            cache_mode=CacheMode.WRITE_ONLY,
        )
        raw_json_str = result.extracted_content
        if not raw_json_str:
            return ""
        try:
            data = json.loads(raw_json_str)
        except json.JSONDecodeError as e:
            print(f"Error parsing extraction JSON for {full_url}: {e}")
            return ""

        texts = []
        if isinstance(data, list):
            for block in data:
                raw_content = block.get("content", "")
                if isinstance(raw_content, list):
                    texts.append(" ".join(raw_content))
                elif isinstance(raw_content, str):
                    texts.append(raw_content)
        else:
            texts.append(str(data))
        return "\n".join(texts)

async def main():
    # Load unprocessed articles
    unprocessed_articles = get_unprocessed_articles()

    extracted_contents = {}
    for article in unprocessed_articles:
        article_id = article["id"]
        # Normalize URL: use article["url"] if it starts with http; otherwise, prepend "https://www."
        url = article["url"]
        article_url = url if url.startswith("http") else "https://www." + url
        print(f"Extracting content from {article_url}")
        try:
            extracted_content = await extract_main_content(article_url)
        except Exception as e:
            print(f"[ERROR] Failed to extract content from {article_url}: {e}")
            extracted_content = ""
        extracted_contents[article_id] = extracted_content

    # Store extracted contents
    with open("extracted_contents.json", "w") as f:
        json.dump(extracted_contents, f, indent=2)
    print("Content extraction complete.")

if __name__ == "__main__":
    asyncio.run(main())
