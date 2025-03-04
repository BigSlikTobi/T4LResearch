import json
from urllib.parse import urlparse
from datetime import datetime, timedelta, timezone
from createArticles.detectTeam import detectTeam
from createArticles.fetchUnprocessedArticles import get_unprocessed_articles, supabase_client
# Import functions from their new location
from createArticles.statusManagement import update_article_statuses, update_missing_statuses, cleanup_archived_articles

def create_news_article_record(
    article: dict,
    english_data: dict,
    german_data: dict,
    image_data: dict,
    is_reviewed: bool = False,  # Add parameter with default False
    topic_id: int = None  # Add topic_id parameter
) -> int:
    """
    Inserts a new record into 'NewsArticle'.
    'english_data', 'german_data', and 'image_data' should each be a dict containing
    the respective fields.
    This version also detects the team name from the English article content.
    Returns the ID of the newly created record or None on failure.
    
    Args:
        article: Source article data
        english_data: English translation data
        german_data: German translation data
        image_data: Image metadata
        is_reviewed: Whether the article has been reviewed/cleaned
        topic_id: The topic ID to assign to this article
    """
    try:
        # Extract base URL from imageSource for imageAttribution
        image_source_url = image_data.get("url", "")  # Changed from imageSource to url
        parsed_url = urlparse(image_source_url)
        base_image_url = parsed_url.scheme + "://" + parsed_url.netloc if parsed_url.netloc else image_source_url

        # Instantiate detectTeam and detect the team from the English article content.
        team_detector = detectTeam()  # CHANGED
        team_detection = team_detector.detect_team(english_data.get("content", ""))  # CHANGED
        team_name = team_detection.get("team", "")
        
        # Get the topic name if a topic ID is provided
        topic_name = None
        if topic_id:
            try:
                # Fetch the topic name from the Topics table
                topic_response = supabase_client.table("Topics").select("TopicName").eq("id", topic_id).execute()
                if topic_response.data and len(topic_response.data) > 0:
                    topic_name = topic_response.data[0]["TopicName"]
                    print(f"Resolved topic ID {topic_id} to name: '{topic_name}'")
            except Exception as e:
                print(f"Error fetching topic name for ID {topic_id}: {e}")

        # Build the record to insert, now including the team field.
        record_to_insert = {
            "NewsResult": article.get("uniqueName"),
            "sourceURL": article.get("url"),
            "sourceArticlePublishedAt": article.get("publishedAt"),
            "sourceArticleUpdatedAt": article.get("publishedAt"),
            "sourceAutor": article.get("author", "Unknown"),
            "EnglishHeadline": english_data.get("headline", ""),
            "EnglishArticle": english_data.get("content", ""),
            "GermanHeadline": german_data.get("headline", ""),
            "GermanArticle": german_data.get("content", ""),
            "imageUrl": image_data.get("image", ""),  # Changed from imageURL to image
            "imageAltText": image_data.get("imageAltText", ""),
            "imageSource": image_data.get("url", ""),  # Changed from imageSource to url
            "imageAttribution": base_image_url,
            "isHeadline": False,  # Assuming default value is false.
            "Team": team_name,
            "isReviewed": is_reviewed,  # Use the parameter instead of hardcoding False
            "Status": "NEW",  # Adding Status field with default value "NEW"
            "Topic": topic_name  # Use the topic name instead of ID
        }

        # CHANGED: use direct access to result.data
        result = supabase_client.table("NewsArticle").insert([record_to_insert]).execute()
        if result.data:
            new_id = result.data[0]["id"]
            print(f"Created new record in 'NewsArticle' table with ID: {new_id}")
            if topic_name:
                print(f"Article assigned to topic: '{topic_name}'")
            return new_id
        else:
            print("Failed to create new record: No data returned from insert operation.")
            return None
    except Exception as e:
        print(f"Error creating record in 'NewsArticle' table: {e}")
        return None

def mark_article_as_processed(article_id: int):
    """
    Marks the article as processed in 'NewsResults' table by setting isProcessed = True.
    """
    try:
        # CHANGED: use supabase_client for DB operations
        supabase_client.table("NewsResults").update({"isProcessed": True}).eq("id", article_id).execute()
        print(f"Article ID {article_id} marked as processed.")
    except Exception as e:
        print(f"Error marking article {article_id} as processed: {e}")

def process_articles(unprocessed_articles, english_articles, german_articles, images_data):
    """Main function to process and store articles in the database."""
    for article in unprocessed_articles:
        article_id = article["id"]
        print(f"\nStoring data for article ID: {article_id}")

        # Convert integer ID to string if your JSON uses string keys
        str_id = str(article_id)

        # Get the English and German data for this article
        english_data = english_articles.get(str_id, {"headline": "", "content": ""})
        german_data = german_articles.get(str_id, {"headline": "", "content": ""})
        image_data = images_data.get(str_id, {
            "image": "",  # Changed from imageURL to image
            "imageAltText": "",
            "url": "",  # Changed from imageSource to url
            "imageAttribution": ""
        })

        # Create the record in 'NewsArticle'
        new_record_id = create_news_article_record(article, english_data, german_data, image_data)

        # If insertion succeeded, mark the article as processed
        if new_record_id:
            mark_article_as_processed(article_id)

if __name__ == '__main__':
    # Load all necessary data
    unprocessed_articles = get_unprocessed_articles()
    
    with open("English_articles.json", "r", encoding='utf-8') as f:
        english_articles = json.load(f)
    with open("German_articles.json", "r", encoding='utf-8') as f:
        german_articles = json.load(f)
    with open("images.json", "r", encoding='utf-8') as f:
        images_data = json.load(f)

    process_articles(unprocessed_articles, english_articles, german_articles, images_data)
    print("Data storage complete.")
    
    # Run the cleanup function
    print("\nStarting cleanup of archived articles...")
    cleanup_archived_articles()
    
    # Then run regular status updates
    print("\nRunning regular status updates...")
    update_missing_statuses()
    update_article_statuses()
