import asyncio
from fetchUnprocessedArticles import get_unprocessed_articles
from extractContent import extract_main_content
from relatedArticles import process_source_article
from englishArticle import generate_english_article
from germanArticle import generate_german_article
from getImage import search_image
from storeInDB import create_news_article_record, mark_article_as_processed

async def process_article(article):
    article_id = article["id"]
    print(f"\n=== Processing article ID: {article_id} ===")
    
    # 1. Extract the main content
    url = article["url"] if article["url"].startswith("http") else "https://www." + article["url"]
    extracted_content = await extract_main_content(url)
    if not extracted_content:
        print(f"Content extraction failed for article {article_id}")
        return

    # 2. Fetch related articles (if any)
    # process_source_article returns a dict like { article_id: [related_articles] }
    related_dict = await process_source_article(str(article_id), extracted_content)
    related_articles = related_dict.get(str(article_id), [])
    
    # 3. Generate English article
    english_data = await generate_english_article(extracted_content, related_articles, verbose=True)
    
    # 4. Generate German article
    german_data = await generate_german_article(extracted_content, related_articles, verbose=True)
    
    # 5. Search for an image
    image_data = await search_image(extracted_content)
    
    # 6. Store the result in the database and mark as processed
    new_record_id = create_news_article_record(article, english_data, german_data, image_data)
    if new_record_id:
        mark_article_as_processed(article_id)
    else:
        print(f"Failed to store article {article_id} in the DB.")

async def main():
    # Fetch all unprocessed articles
    articles = get_unprocessed_articles()
    if not articles:
        print("No unprocessed articles found.")
        return

    # Process each article sequentially
    for article in articles:
        await process_article(article)

if __name__ == "__main__":
    asyncio.run(main())
