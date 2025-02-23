import asyncio
import math
from fetchUnprocessedArticles import get_unprocessed_articles
from extractContent import extract_main_content
from relatedArticles import process_source_article
from englishArticle import generate_english_article
from germanArticle import generate_german_article
from getImage import search_image  # Assumes getImage.py exists and provides search_image.
from storeInDB import create_news_article_record, mark_article_as_processed

# --- Helper functions for similarity grouping ---
def cosine_similarity(vec1: list, vec2: list) -> float:
    """Compute the cosine similarity between two vectors."""
    dot = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)

def group_similar_articles(articles: list, threshold: float = 0.85) -> list:
    """
    Group articles based on the similarity of their embedding vectors.
    Articles that exceed the similarity threshold are combined into one group.
    """
    groups = []
    visited = set()
    for article in articles:
        article_id = article["id"]
        if article_id in visited:
            continue
        group = [article]
        visited.add(article_id)
        for other in articles:
            other_id = other["id"]
            if other_id in visited:
                continue
            vec1 = article.get("embedding", [])
            vec2 = other.get("embedding", [])
            # If either article lacks an embedding, skip comparison.
            if not vec1 or not vec2:
                continue
            sim = cosine_similarity(vec1, vec2)
            if sim > threshold:
                group.append(other)
                visited.add(other_id)
        groups.append(group)
    return groups

# --- Processing a group of similar articles ---
async def process_article_group(article_group: list):
    """
    Process a group of similar articles by combining their content and related background articles.
    Generate a single English and German article for the combined content.
    """
    combined_content = ""
    combined_related = []
    
    for article in article_group:
        article_id = article["id"]
        url = article["url"] if article["url"].startswith("http") else "https://www." + article["url"]
        print(f"Extracting content from {url} (Article ID: {article_id})")
        content = await extract_main_content(url)
        if content:
            combined_content += content + "\n"
        # Fetch related background articles for this article.
        related_dict = await process_source_article(str(article_id), content)
        related_articles = related_dict.get(str(article_id), [])
        combined_related.extend(related_articles)
    
    if not combined_content.strip():
        print("No content extracted for this group, skipping...")
        return
    
    print("Generating combined English article...")
    english_data = await generate_english_article(combined_content, combined_related, verbose=True)
    
    print("Generating combined German article...")
    german_data = await generate_german_article(combined_content, combined_related, verbose=True)
    
    print("Searching for image for combined content...")
    image_data = await search_image(combined_content)
    
    # Use the first article in the group as the representative record.
    representative_article = article_group[0]
    new_record_id = create_news_article_record(representative_article, english_data, german_data, image_data)
    if new_record_id:
        for article in article_group:
            mark_article_as_processed(article["id"])
    else:
        print("Failed to store the combined article in the DB.")

# --- Main pipeline ---
async def main():
    articles = get_unprocessed_articles()
    if not articles:
        print("No unprocessed articles found.")
        return

    # Group similar articles using the embedding similarity.
    groups = group_similar_articles(articles, threshold=0.85)
    print(f"Found {len(groups)} group(s) of similar articles.")
    
    # Process each group sequentially.
    for group in groups:
        group_ids = [article["id"] for article in group]
        print(f"\nProcessing group with article IDs: {group_ids}")
        await process_article_group(group)

if __name__ == "__main__":
    asyncio.run(main())
