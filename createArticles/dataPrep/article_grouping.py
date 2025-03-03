import sys
import os
import asyncio

# Add the parent directory to the Python path to allow for absolute imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from createArticles.dataPrep.similarity import cosine_similarity, check_for_similar_articles
from createArticles.storeInDB import mark_article_as_processed
# Import from our new contentGeneration package
from createArticles.contentGeneration import process_content

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
    # Check if there's an exact similar article first - this should take precedence
    for article in article_group:
        if "Status" not in article:  # This is a new article
            is_similar = await check_for_similar_articles(article)
            if is_similar:
                print(f"Article {article['uniqueName']} was processed by similarity check, skipping normal processing.")
                # Mark all articles in the group as processed
                for a in article_group:
                    mark_article_as_processed(a["id"])
                return
    
    # Use the new content processing pipeline from contentGeneration package
    await process_content(article_group)