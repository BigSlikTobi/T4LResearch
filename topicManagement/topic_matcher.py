"""
Module for matching articles with topics.

This module handles the logic of determining whether an article's content
aligns with any of the defined topics in the Topics table.
"""

import os
import sys
import asyncio
from typing import List, Dict, Any, Optional, Tuple
import json
from dotenv import load_dotenv
from openai import OpenAI
import traceback

# Add parent directory to Python path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from supabase import create_client, Client
from LLMSetup import initialize_model
from .topic_fetcher import fetch_active_topics

# Load environment variables
load_dotenv()

# Initialize Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Initialize OpenAI client directly
openai_api_key = os.getenv("OPENAI_API_KEY")
openai_client = OpenAI(api_key=openai_api_key)

# Also initialize through LLMSetup for compatibility
model_info = initialize_model("openai")
openai_provider = model_info["model_name"]

def match_article_with_topics(article_content: str, article_headline: str, topics: List[Dict]) -> Optional[Dict]:
    """
    Matches an article's content with the available topics.
    
    Args:
        article_content (str): The main content of the article
        article_headline (str): The headline of the article
        topics (List[Dict]): List of topics to match against
        
    Returns:
        Optional[Dict]: The matched topic or None if no match found
    """
    if not topics:
        print("No topics available for matching")
        return None
        
    # Combine headline and content for better matching
    full_content = f"{article_headline}\n\n{article_content}"
    
    best_match = None
    best_score = 0
    
    for topic in topics:
        topic_name = topic.get("TopicName", "")
        topic_keywords = topic.get("Keywords", [])
        topic_description = topic.get("Description", "")
        
        # Count keyword matches
        keyword_count = 0
        for keyword in topic_keywords:
            keyword_lower = keyword.lower()
            if keyword_lower in full_content.lower():
                keyword_count += 1
        
        # Calculate match score based on keyword frequency
        score = keyword_count / len(topic_keywords) if topic_keywords else 0
        
        # If good initial match (at least 30% of keywords), use LLM for confirmation
        if score >= 0.3:
            llm_match = _confirm_match_with_llm(full_content, topic_name, topic_description, topic_keywords)
            
            if llm_match:
                # Boost score if LLM confirms it's a good match
                score += 0.3
                
        # Track best match
        if score > best_score and score >= 0.5:  # Threshold for accepting a match
            best_score = score
            best_match = topic
            print(f"Found potential topic match: {topic_name} with score {score:.2f}")
    
    return best_match

def _confirm_match_with_llm(article_content: str, topic_name: str, topic_description: str, 
                           topic_keywords: List[str]) -> bool:
    """
    Uses LLM to confirm if the article is truly about the matched topic.
    
    Args:
        article_content (str): Combined headline and content
        topic_name (str): The name of the topic
        topic_description (str): The description of the topic
        topic_keywords (List[str]): Keywords associated with the topic
        
    Returns:
        bool: True if the LLM confirms it's a good match, False otherwise
    """
    # Use a shorter version of the article content to save tokens
    max_content_length = 1500
    shortened_content = article_content[:max_content_length] + "..." if len(article_content) > max_content_length else article_content
    
    # Create the prompt
    prompt = f"""
    You are an expert in topic classification. Analyze the following article content and determine 
    if it's genuinely related to the topic "{topic_name}".

    Topic description: {topic_description}
    
    Topic keywords: {', '.join(topic_keywords)}
    
    Article content (excerpt):
    {shortened_content}
    
    Is this article primarily about the {topic_name} topic? Consider:
    1. Does the article directly discuss the central aspects of the topic?
    2. Is the topic a main focus rather than just a brief mention?
    3. Would a reader interested in this topic find this article valuable?
    
    Respond with a JSON object containing a single field "is_match" with a boolean value.
    """
    
    try:
        # Use the direct OpenAI client
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",  # Using a cost-effective but capable model
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,  # Low temperature for more deterministic responses
            response_format={"type": "json_object"}
        )
        
        # Extract the content from the response
        result_text = response.choices[0].message.content
        
        try:
            # Parse the JSON response
            result = json.loads(result_text)
            is_match = result.get("is_match", False)
            
            print(f"LLM confirmation for topic '{topic_name}': {is_match}")
            return is_match
            
        except json.JSONDecodeError:
            print(f"Error parsing LLM response: {result_text}")
            return False
            
    except Exception as e:
        print(f"Error calling LLM API: {e}")
        return False

async def update_article_topic(article_id: int, topic_name: str) -> bool:
    """
    Updates an article with the matched topic name.
    
    Args:
        article_id (int): The ID of the article to update
        topic_name (str): The name of the matched topic
        
    Returns:
        bool: True if update was successful, False otherwise
    """
    try:
        print(f"\nAttempting to update article {article_id} with topic '{topic_name}'...")
        
        # First verify the article exists
        check_response = supabase_client.table("NewsArticle").select("id", "Topic").eq("id", article_id).execute()
        if not check_response.data:
            print(f"Article {article_id} not found in database")
            return False
        
        current_topic = check_response.data[0].get("Topic")
        print(f"Current topic for article {article_id}: '{current_topic}'")
        
        # Attempt the update
        print(f"Executing update query...")
        response = supabase_client.table("NewsArticle").update({
            "Topic": topic_name
        }).eq("id", article_id).execute()
        
        # Log the response data
        print(f"Update response data: {json.dumps(response.data, indent=2)}")
        
        # Check if update was successful (data contains the updated record)
        success = len(response.data) > 0
        if success:
            print(f"Successfully updated article {article_id} with topic name: '{topic_name}'")
            
            # Verify the update
            verify_response = supabase_client.table("NewsArticle").select("Topic").eq("id", article_id).execute()
            if verify_response.data:
                updated_topic = verify_response.data[0].get("Topic")
                print(f"Verified topic after update: '{updated_topic}'")
                if updated_topic != topic_name:
                    print(f"Warning: Topic verification failed. Expected '{topic_name}' but found '{updated_topic}'")
                    return False
        else:
            print(f"Failed to update article {article_id} with topic name: '{topic_name}'")
        
        return success
    except Exception as e:
        print(f"Error updating article {article_id} with topic:")
        print(f"Exception: {str(e)}")
        print("Traceback:")
        print(traceback.format_exc())
        return False

async def process_article(article_id: int) -> bool:
    """
    Processes a single article to find and assign a matching topic.
    
    Args:
        article_id (int): The ID of the article to process
        
    Returns:
        bool: True if processing was successful, False otherwise
    """
    try:
        print(f"\nProcessing article {article_id}...")
        # Fetch the article
        response = supabase_client.table("NewsArticle").select("id", "EnglishHeadline", "EnglishArticle").eq("id", article_id).execute()
        
        if not response.data or len(response.data) == 0:
            print(f"No article found with ID {article_id}")
            return False
        
        article = response.data[0]
        headline = article.get("EnglishHeadline", "")
        content = article.get("EnglishArticle", "")
        
        print(f"Found article: {headline}")
        
        # Fetch active topics
        topics = fetch_active_topics()
        print(f"Fetched {len(topics)} active topics for matching")
        
        # Match with topics
        matched_topic = match_article_with_topics(content, headline, topics)
        
        if matched_topic:
            topic_id = matched_topic.get("id")
            topic_name = matched_topic.get("TopicName")
            print(f"Matched article {article_id} with topic '{topic_name}' (ID: {topic_id})")
            
            # Update the article with the matched topic name
            success = await update_article_topic(article_id, topic_name)
            print(f"Topic update {'succeeded' if success else 'failed'}")
            return success
        else:
            print(f"No matching topic found for article {article_id}")
            return True  # Consider this a successful process, just with no match
            
    except Exception as e:
        print(f"Error processing article {article_id}:")
        print(f"Exception: {str(e)}")
        print("Traceback:")
        print(traceback.format_exc())
        return False

async def process_all_articles() -> Tuple[int, int]:
    """
    Processes all relevant articles that haven't been assigned a topic yet.
    
    Returns:
        Tuple[int, int]: (processed_count, matched_count)
    """
    try:
        # Fetch articles that don't have a topic assigned (Topic IS NULL)
        response = supabase_client.table("NewsArticle").select("id").is_("Topic", "null").execute()
        
        if not response.data or len(response.data) == 0:
            print("No articles found without topics")
            return (0, 0)
        
        article_ids = [article.get("id") for article in response.data]
        print(f"Found {len(article_ids)} articles without topics")
        
        processed_count = 0
        matched_count = 0
        
        # Process each article
        for article_id in article_ids:
            result = await process_article(article_id)
            if result:
                processed_count += 1
                # Check if topic was actually assigned
                check_response = supabase_client.table("NewsArticle").select("Topic").eq("id", article_id).execute()
                if check_response.data and check_response.data[0].get("Topic") is not None:
                    matched_count += 1
        
        print(f"Processed {processed_count} articles, matched {matched_count} with topics")
        return (processed_count, matched_count)
        
    except Exception as e:
        print(f"Error processing articles: {e}")
        return (0, 0)

async def update_articles_with_topic_names() -> Tuple[int, int]:
    """
    Update all articles that have a numeric topic ID to use the topic name instead.
    
    This function finds all articles with a numeric Topic value, looks up the 
    corresponding TopicName from the Topics table, and updates the article to store
    the topic name instead of the ID.
    
    Returns:
        Tuple[int, int]: (processed_count, updated_count)
    """
    try:
        # Fetch all topics to have a mapping of IDs to names
        topics_response = supabase_client.table("Topics").select("*").execute()
        
        if not topics_response.data:
            print("No topics found in the database.")
            return (0, 0)
            
        # Create a mapping of topic IDs to names
        topic_map = {topic["id"]: topic["TopicName"] for topic in topics_response.data}
        
        # Fetch all articles with a numeric Topic value
        articles_response = supabase_client.table("NewsArticle").select("id", "Topic").execute()
        
        if not articles_response.data:
            print("No articles found in the database.")
            return (0, 0)
            
        processed_count = 0
        updated_count = 0
        
        # Process each article
        for article in articles_response.data:
            article_id = article.get("id")
            topic_value = article.get("Topic")
            
            # Check if topic_value is a numeric string or int
            if topic_value is not None and (isinstance(topic_value, int) or (isinstance(topic_value, str) and topic_value.isdigit())):
                topic_id = int(topic_value)
                
                if topic_id in topic_map:
                    topic_name = topic_map[topic_id]
                    print(f"Updating article {article_id}: Topic ID {topic_id} → Topic name '{topic_name}'")
                    
                    # Update the article with the topic name
                    update_response = supabase_client.table("NewsArticle").update({
                        "Topic": topic_name
                    }).eq("id", article_id).execute()
                    
                    if update_response.data:
                        updated_count += 1
                else:
                    print(f"Warning: Article {article_id} has topic ID {topic_id} which doesn't exist in Topics table")
                    
                processed_count += 1
        
        print(f"Processed {processed_count} articles, updated {updated_count} with topic names")
        return (processed_count, updated_count)
        
    except Exception as e:
        print(f"Error updating articles with topic names: {e}")
        return (0, 0)

async def identify_article_topic(article_headline: str, article_content: str) -> Optional[int]:
    """
    Identifies a topic for an article's content and returns the topic ID.
    This is used during article creation to assign a topic immediately.
    
    Args:
        article_headline (str): The headline of the article
        article_content (str): The main content of the article
        
    Returns:
        Optional[int]: The ID of the matched topic or None if no match found
    """
    try:
        print(f"\nIdentifying topic for new article: {article_headline[:50]}...")
        
        # Fetch active topics
        topics = fetch_active_topics()
        print(f"Fetched {len(topics)} active topics for matching")
        
        if not topics:
            print("No topics available for matching")
            return None
        
        # Match with topics
        matched_topic = match_article_with_topics(article_content, article_headline, topics)
        
        if matched_topic:
            topic_id = matched_topic.get("id")
            topic_name = matched_topic.get("TopicName")
            print(f"Identified topic '{topic_name}' (ID: {topic_id}) for new article")
            return topic_id
        else:
            print(f"No matching topic found for new article")
            return None
            
    except Exception as e:
        print(f"Error identifying topic for new article:")
        print(f"Exception: {str(e)}")
        print("Traceback:")
        print(traceback.format_exc())
        return None
        
if __name__ == "__main__":
    # Run standalone test when called directly
    asyncio.run(process_all_articles())