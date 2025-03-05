import sys
import os
import asyncio

# Add the parent directory to the Python path to allow for absolute imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from createArticles.extractContent import extract_main_content
from createArticles.relatedArticles import process_source_article
from createArticles.contentGeneration.article_generation import (
    generate_article_content, 
    extract_keywords_from_content,
    extract_keywords_from_summary,
    combine_keywords
)
from createArticles.contentGeneration.image_processing import (
    find_article_image,
    use_existing_image
)
from createArticles.contentGeneration.db_operations import (
    create_new_article,
    update_existing_article,
    mark_articles_as_processed
)

async def extract_article_content(article):
    """
    Extract content from an article URL.
    
    Args:
        article (dict): Article data including URL
        
    Returns:
        tuple: (content, related_articles)
    """
    article_id = article["id"]
    url = article["url"] if article["url"].startswith("http") else "https://www." + article["url"]
    
    print(f"Extracting content from {url} (Article ID: {article_id})")
    content = await extract_main_content(url)
    
    # Fetch related background articles
    related_dict = await process_source_article(str(article_id), content)
    related_articles = related_dict.get(str(article_id), [])
    
    return content, related_articles

async def process_content(article_group):
    """
    Main content processing pipeline that handles extracting content, generating articles,
    finding images, and storing/updating database records.
    
    This is the core value-adding process that takes raw articles and produces
    the final English and German articles with images.
    
    Args:
        article_group (list): Group of similar articles to process together
        
    Returns:
        tuple: (processed_news_result_ids, news_article_ids) - Lists of processed NewsResult IDs and the corresponding NewsArticle IDs
    """
    combined_content = ""
    combined_related = []
    combined_keywords = set()
    existing_article = None
    article_ids = [article["id"] for article in article_group]
    
    # Identify if there's an existing article in the group
    for article in article_group:
        if "Status" in article:  # This indicates it's an existing article
            existing_article = article
            break
    
    # Process each article in the group
    for article in article_group:
        # Skip content extraction for existing articles as we already have their content
        if "Status" in article:
            combined_content += article.get("EnglishArticle", "") + "\n"
            continue
        
        # Extract content and related articles
        content, related_articles = await extract_article_content(article)
        
        if content:
            combined_content += content + "\n"
            combined_related.extend(related_articles)
            
        # Extract keywords from various sources
        if isinstance(article, dict):
            # Add existing keywords if available
            if "keywords" in article and article["keywords"]:
                combined_keywords.update(article["keywords"])
                
            # Extract keywords from summary
            if "summary" in article and article["summary"]:
                summary_keywords = await extract_keywords_from_summary(article["summary"])
                combined_keywords.update(summary_keywords)
                
            # Extract keywords from content
            if content:
                content_keywords = await extract_keywords_from_content(content)
                combined_keywords.update(content_keywords)
    
    # Skip if no content was extracted
    if not combined_content.strip():
        print("No content extracted for this group, skipping...")
        return [], []
    
    # Convert keywords set to list
    final_keywords = list(combined_keywords)
    
    # Generate English and German article content
    english_data, german_data = await generate_article_content(
        combined_content, 
        combined_related,
        verbose=False
    )
    
    # Process differently based on whether we're updating an existing article or creating a new one
    if existing_article:
        # Use existing article's headlines and image data
        english_data["headline"] = existing_article["EnglishHeadline"]
        german_data["headline"] = existing_article["GermanHeadline"]
        
        # Use the existing image
        image_data = use_existing_image(existing_article)
        
        # Update the existing article in the database
        update_success = await update_existing_article(
            existing_article["id"], 
            english_data, 
            german_data
        )
        
        # Mark new articles as processed if update was successful
        if update_success:
            print(f"Updated article {existing_article['id']} passed review")
            # Mark all new articles in the group as processed
            new_article_ids = [article["id"] for article in article_group if "Status" not in article]
            mark_articles_as_processed(new_article_ids)
            # Return the new article IDs and the existing article ID
            return new_article_ids, [existing_article["id"]]
        else:
            print(f"Updated article {existing_article['id']} failed review - not marking as processed")
            return [], []
    
    else:
        # Handle completely new article group - find an image
        image_data = await find_article_image(combined_content, final_keywords)
        
        # Use the first article in the group as the representative record
        representative_article = article_group[0]
        
        # Create a new article record without topic assignment
        new_record_id = await create_new_article(
            representative_article,
            english_data,
            german_data,
            image_data,
            is_reviewed=True,
            topic_id=None  # No topic assignment
        )
        
        # If article was created and passed review, mark all articles in group as processed
        if new_record_id:
            processed_ids = [article["id"] for article in article_group]
            mark_articles_as_processed(processed_ids)
            # Return the processed article IDs and the new record ID
            return processed_ids, [new_record_id]
        
        return [], []