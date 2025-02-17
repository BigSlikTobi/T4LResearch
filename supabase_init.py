# supabase_init.py
import os
import json
import logging
from supabase import create_client, Client  # Import Client
from urllib.parse import urlparse
from createArticles.detectTeam import detectTeam  # Relative import

logging.basicConfig(level=logging.INFO)

class SupabaseClient:
    def __init__(self) -> None:
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")
        if not supabase_url or not supabase_key:
            raise EnvironmentError("Supabase credentials are not set in the environment.")
        self.client = create_client(supabase_url, supabase_key)
        self.team_detector = detectTeam()

    def post_new_source_article_to_supabase(self, article: dict) -> None: # Changed to dict
        # Use the 'id' key as fallback for 'uniqueName'
        unique_name = article.get("uniqueName", article.get("id"))
        publishedAt = article.get("publishedAt", article.get("published_at"))
        payload = {
            "uniqueName": unique_name,
            "source": article["source"],
            "headline": article["headline"],
            "href": article["href"],
            "url": article["url"],
            "publishedAt": publishedAt,
            "isProcessed": article.get("isProcessed", False),
        }
        try:
            response = self.client.table("NewsResults").insert(payload).execute() # Removed list
            logging.info(f"Successfully posted: {unique_name}")
        except Exception as e:
            logging.error(f"Error posting {unique_name}: {e}")

    def create_news_article_record(self, article: dict, english_data: dict,
                                     german_data: dict, image_data: dict) -> int:
        try:
            image_source_url = image_data.get("imageSource", "")
            parsed_url = urlparse(image_source_url)
            base_image_url = f"{parsed_url.scheme}://{parsed_url.netloc}" if parsed_url.netloc else image_source_url
            team_detection = self.team_detector.detect_team(english_data.get("content", ""))
            team_name = team_detection.get("team", "")
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
                "imageUrl": image_data.get("imageURL", ""),
                "imageAltText": image_data.get("imageAltText", ""),
                "imageSource": image_data.get("imageSource", ""),
                "imageAttribution": base_image_url,
                "isHeadline": False,
                "Team": team_name
            }
            response = self.client.table("NewsArticle").insert(record_to_insert).execute()  # Removed list here too
            if response and len(response.data) > 0:  # Access data attribute
                new_id = response.data[0].get("id") # Access data attribute
                logging.info(f"Created new record in 'NewsArticle' table with ID: {new_id}")
                return new_id
            else:
                logging.error("Failed to create new record: No data returned from insert operation.")
                return None
        except Exception as e:
            logging.error(f"Error creating record in 'NewsArticle' table: {e}")
            return None

    def mark_article_as_processed(self, article_id: int) -> None:
        try:
            # Assuming 'article_id' corresponds to the 'uniqueName' in NewsResults
            response = self.client.table("NewsResults").update({"isProcessed": True}).eq("uniqueName", article_id).execute()
            if response and response.data: # Check if the response is valid and contains data
               logging.info(f"Article ID {article_id} marked as processed.")
            else:
                logging.warning(f"Article ID {article_id} not found or already processed.")


        except Exception as e:
            logging.error(f"Error marking article {article_id} as processed: {e}")

if __name__ == "__main__":
    supabase = SupabaseClient()
    with open("unprocessed_articles.json", "r") as f:
        unprocessed_articles = json.load(f)
    with open("English_articles.json", "r", encoding="utf-8") as f:
        english_articles = json.load(f)
    with open("German_articles.json", "r", encoding="utf-8") as f:
        german_articles = json.load(f)
    with open("images.json", "r", encoding="utf-8") as f:
        images_data = json.load(f)
    for article in unprocessed_articles:
        # article_id is now the uniqueName (which should be unique)
        article_id = article["uniqueName"]
        logging.info(f"Storing data for article ID: {article_id}")
        str_id = str(article["id"]) # Keep using the original 'id' for filenames
        english_data = english_articles.get(str_id, {"headline": "", "content": ""})
        german_data = german_articles.get(str_id, {"headline": "", "content": ""})
        image_data = images_data.get(str_id, {
            "imageURL": "",
            "imageAltText": "",
            "imageSource": "",
            "imageAttribution": ""
        })
        new_record_id = supabase.create_news_article_record(article, english_data, german_data, image_data)
        if new_record_id:
            supabase.mark_article_as_processed(article_id)
    logging.info("Data storage complete.")