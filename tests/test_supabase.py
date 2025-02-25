import os
import pytest
from dotenv import load_dotenv
from supabase_init import SupabaseClient

# Load environment variables from .env file
load_dotenv()

@pytest.mark.supabase
def test_post_new_source_article():
    # Initialize Supabase client with credentials
    supabase = SupabaseClient()
    
    # Prepare test data with the required fields
    test_entry = {
        "id": "test_id_1234",
        "source": "https://example.com/",
        "headline": "Test Headline",
        "href": "test-article",
        "published_at": "2023-10-15T00:00:00Z"
    }
    
    try:
        # Post the test entry
        supabase.post_new_source_article_to_supabase([test_entry])
        
        # Verify the entry was created
        response = supabase.client.table("NewsResults").select("*").eq("uniqueName", test_entry["id"]).execute()
        assert len(response.data) == 1, "Test entry was not created"
        
    finally:
        # Clean up: Remove the test entry after posting
        supabase.client.table("NewsResults").delete().eq("uniqueName", test_entry["id"]).execute()

@pytest.mark.supabase
def test_create_news_article_record():
    supabase = SupabaseClient()
    
    # Test data
    test_article = {
        "uniqueName": "test_article_123",
        "url": "https://test.com/article",
        "publishedAt": "2024-01-01T12:00:00Z",
        "author": "Test Author"
    }
    
    test_english_data = {
        "headline": "Test English Headline",
        "content": "This is a test article about the Bears game."  # Modified to mention Bears
    }
    
    test_german_data = {
        "headline": "Test Deutsche Überschrift",
        "content": "Dies ist ein Testartikel."
    }
    
    test_image_data = {
        "image": "https://test.com/image.jpg",  # Changed from imageURL to image
        "imageAltText": "Test Image",
        "url": "https://test.com",  # Changed from imageSource to url
        "imageAttribution": "Test Attribution"
    }
    
    try:
        # Create the test record
        new_record_id = supabase.create_news_article_record(
            test_article,
            test_english_data,
            test_german_data,
            test_image_data
        )
        
        assert new_record_id is not None, "Failed to create news article record"
        
        # Verify the record exists
        response = supabase.client.table("NewsArticle").select("*").eq("id", new_record_id).execute()
        assert len(response.data) == 1, "Created record not found"
        
        # Verify some key fields
        created_record = response.data[0]
        assert created_record["EnglishHeadline"] == test_english_data["headline"]
        assert created_record["Team"] == "bears"  # Updated expected team
        
    finally:
        # Clean up: Delete the test record
        if 'new_record_id' in locals() and new_record_id:
            supabase.client.table("NewsArticle").delete().eq("id", new_record_id).execute()

