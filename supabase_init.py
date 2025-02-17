import os
import json
import logging
from supabase import create_client
from urllib.parse import urlparse
from createArticles.detectTeam import detectTeam

logging.basicConfig(level=logging.INFO)

class SupabaseClient:
    def __init__(self) -> None:
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")
        if not supabase_url or not supabase_key:
            raise EnvironmentError("Supabase credentials are not set in the environment.")
        self.client = create_client(supabase_url, supabase_key)
        self.team_detector = detectTeam()
    
    def post_new_source_article_to_supabase(self, data: list) -> None:
        for item in data:
            # Use the 'id' key as fallback for 'uniqueName'
            unique_name = item.get("uniqueName", item.get("id"))
            publishedAt = item.get("publishedAt", item.get("published_at"))
            payload = {
                "uniqueName": unique_name,
                "source": item["source"],
                "headline": item["headline"],
                "href": item["href"],
                "url": item["url"],
                "publishedAt": publishedAt,
                "isProcessed": item.get("isProcessed", False),
            }
            try:
                response = self.client.table("NewsResults").insert([payload]).execute()
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
            response = self.client.table("NewsArticle").insert([record_to_insert]).execute()
            if response and len(response) > 1 and response[1]:
                new_id = response[1][0].get("id")
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
            self.client.table("NewsResults").update({"isProcessed": True}).eq("id", article_id).execute()
            logging.info(f"Article ID {article_id} marked as processed.")
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
        article_id = article["id"]
        logging.info(f"Storing data for article ID: {article_id}")
        str_id = str(article_id)
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
