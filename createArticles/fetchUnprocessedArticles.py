import json
from typing import Dict, List
import supabase
from supabase import create_client, Client
import os
from dotenv import load_dotenv

# Load environment variables from .env in project root
load_dotenv("/Users/tobiaslatta/Desktop/Private/T4L/T4LResearch/.env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_unprocessed_articles() -> List[Dict]:
    """
    Fetches NewsResults records where isProcessed = false.
    """
    try:
        response = supabase_client.table("NewsResults").select("*").eq("isProcessed", False).execute()
        return response.data or []
    except Exception as e:
        print(f"Error fetching unprocessed items from Supabase: {e}")
        return []

if __name__ == "__main__":
    unprocessed_articles = get_unprocessed_articles()
    print(f"Found {len(unprocessed_articles)} unprocessed articles.")
