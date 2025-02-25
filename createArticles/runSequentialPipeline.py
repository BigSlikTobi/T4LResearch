import asyncio
import math
from fetchUnprocessedArticles import get_all_active_news
from extractContent import extract_main_content
from relatedArticles import process_source_article
from englishArticle import generate_english_article
from germanArticle import generate_german_article
from getImage import search_image
from storeInDB import create_news_article_record, mark_article_as_processed
from keyword_extractor import KeywordExtractor
from LLMSetup import initialize_model
from review import clean_text, review_article_fields
from supabase_init import SupabaseClient

# Initialize the KeywordExtractor with the OpenAI model
model_config = initialize_model("openai")
keyword_extractor = KeywordExtractor(model_config["model"]["provider"], model_config["model"]["api_key"])
supabase_client = SupabaseClient()

def cosine_similarity(vec1: list, vec2: list) -> float:
    """Compute the cosine similarity between two vectors."""
    dot = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)

def group_similar_articles(new_articles: list, existing_articles: list, threshold: float = 0.85) -> list:
    """
    Group articles based on the similarity of their embedding vectors.
    Now handles both new and existing articles, creating groups that may contain both.
    """
    groups = []
    visited = set()
    
    # First, try to match new articles with existing ones
    for new_article in new_articles:
        new_id = new_article["id"]
        if new_id in visited:
            continue
            
        group = [new_article]
        visited.add(new_id)
        
        # Check against existing articles first
        for existing in existing_articles:
            existing_id = existing["id"]
            if existing_id in visited:
                continue
                
            vec1 = new_article.get("embedding", [])
            vec2 = existing.get("embedding", [])
            if not vec1 or not vec2:
                continue
                
            sim = cosine_similarity(vec1, vec2)
            if sim > threshold:
                group.append(existing)
                visited.add(existing_id)
                break  # Only match with one existing article
                
        # Then check against other new articles
        for other in new_articles:
            other_id = other["id"]
            if other_id in visited:
                continue
                
            vec1 = new_article.get("embedding", [])
            vec2 = other.get("embedding", [])
            if not vec1 or not vec2:
                continue
                
            sim = cosine_similarity(vec1, vec2)
            if sim > threshold:
                group.append(other)
                visited.add(other_id)
                
        groups.append(group)
    
    # Handle remaining new articles that weren't grouped
    for new_article in new_articles:
        if new_article["id"] not in visited:
            groups.append([new_article])
            visited.add(new_article["id"])
    
    return groups

async def process_article_group(article_group: list):
    """
    Process a group of similar articles by combining their content and related background articles.
    Now handles updating existing articles.
    """
    combined_content = ""
    combined_related = []
    combined_keywords = set()
    existing_article = None

    # Identify if there's an existing article in the group
    for article in article_group:
        if "Status" in article:  # This indicates it's an existing article
            existing_article = article
            break

    for article in article_group:
        article_id = article["id"]
        # Skip content extraction for existing articles as we already have their content
        if "Status" in article:
            combined_content += article.get("EnglishArticle", "") + "\n"
            continue
            
        url = article["url"] if article["url"].startswith("http") else "https://www." + article["url"]
        print(f"Extracting content from {url} (Article ID: {article_id})")
        content = await extract_main_content(url)
        if content:
            combined_content += content + "\n"
            
        # Fetch related background articles for new articles only
        related_dict = await process_source_article(str(article_id), content)
        related_articles = related_dict.get(str(article_id), [])
        combined_related.extend(related_articles)
        
        # Extract keywords
        if isinstance(article, dict):
            if "keywords" in article and article["keywords"]:
                combined_keywords.update(article["keywords"])
            if "summary" in article and article["summary"]:
                try:
                    summary_keywords = await keyword_extractor.extract_keywords(article["summary"])
                    combined_keywords.update(summary_keywords)
                except Exception as e:
                    print(f"Error extracting keywords from summary: {e}")
            if content:
                try:
                    content_keywords = await keyword_extractor.extract_keywords(content)
                    combined_keywords.update(content_keywords)
                except Exception as e:
                    print(f"Error extracting keywords from content: {e}")

    if not combined_content.strip():
        print("No content extracted for this group, skipping...")
        return

    final_keywords = list(combined_keywords)
    
    # Generate new article content
    print("Generating combined English article...")
    english_data = await generate_english_article(combined_content, combined_related, verbose=False)
    
    print("Generating combined German article...")
    german_data = await generate_german_article(combined_content, combined_related, verbose=False)
    
    # Clean the generated articles
    english_data["content"] = clean_text(english_data["content"])
    german_data["content"] = clean_text(german_data["content"])
    
    if existing_article:
        # Use existing article's headlines and image data
        english_data["headline"] = existing_article["EnglishHeadline"]
        german_data["headline"] = existing_article["GermanHeadline"]
        image_data = {
            "image": existing_article["imageUrl"],
            "imageAltText": existing_article["imageAltText"],
            "url": existing_article["imageSource"],
            "imageAttribution": existing_article["imageAttribution"]
        }
        # Update the existing article
        record_to_update = {
            "EnglishArticle": english_data["content"],
            "GermanArticle": german_data["content"],
            "Status": "UPDATED"
        }
        try:
            supabase_client.client.table("NewsArticle")\
                .update(record_to_update)\
                .eq("id", existing_article["id"])\
                .execute()
            print(f"Updated existing article {existing_article['id']} with new content")
            
            # Mark all new articles in the group as processed
            for article in article_group:
                if "Status" not in article:  # Only mark new articles
                    mark_article_as_processed(article["id"])
        except Exception as e:
            print(f"Error updating existing article: {e}")
    else:
        # Handle completely new article group
        print("Searching for image for combined content...")
        image_data = await search_image(combined_content, final_keywords)
        
        # Use the first article in the group as the representative record
        representative_article = article_group[0]
        new_record_id = create_news_article_record(
            representative_article, 
            english_data, 
            german_data, 
            image_data,
            is_reviewed=True  # Mark as reviewed since we've cleaned the text
        )
        
        if new_record_id:
            review_passed = await review_article_fields(new_record_id, representative_article["uniqueName"])
            if review_passed:
                for article in article_group:
                    mark_article_as_processed(article["id"])
            else:
                print("Article failed review process")
        else:
            print("Failed to store the combined article in the DB.")

async def main():
    # Get both unprocessed and active articles
    unprocessed_articles, active_articles = get_all_active_news()
    
    if not unprocessed_articles:
        print("No unprocessed articles found.")
        return

    # Group similar articles, now considering both new and existing articles
    groups = group_similar_articles(unprocessed_articles, active_articles, threshold=0.85)
    print(f"Found {len(groups)} group(s) of similar articles.")
    
    # Process each group sequentially
    for group in groups:
        group_ids = [article["id"] for article in group]
        print(f"\nProcessing group with article IDs: {group_ids}")
        await process_article_group(group)

if __name__ == "__main__":
    asyncio.run(main())
