import sys
import os

# Add the parent directory to the Python path to allow for absolute imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from createArticles.englishArticle import generate_english_article
from createArticles.germanArticle import generate_german_article
from createArticles.review import clean_text
from createArticles.keyword_extractor import KeywordExtractor
from LLMSetup import initialize_model

# Initialize the KeywordExtractor with the OpenAI model
model_config = initialize_model("openai")
keyword_extractor = KeywordExtractor(model_config["model"]["provider"], model_config["model"]["api_key"])

async def extract_keywords_from_content(content):
    """
    Extract keywords from content text.
    """
    try:
        return await keyword_extractor.extract_keywords(content)
    except Exception as e:
        print(f"Error extracting keywords from content: {e}")
        return []

async def extract_keywords_from_summary(summary):
    """
    Extract keywords from article summary.
    """
    try:
        return await keyword_extractor.extract_keywords(summary)
    except Exception as e:
        print(f"Error extracting keywords from summary: {e}")
        return []

async def generate_article_content(combined_content, combined_related_articles, verbose=False):
    """
    Generate both English and German article content.
    Returns a tuple of (english_data, german_data)
    """
    print("Generating combined English article...")
    english_data = await generate_english_article(combined_content, combined_related_articles, verbose=verbose)
    
    print("Generating combined German article...")
    german_data = await generate_german_article(combined_content, combined_related_articles, verbose=verbose)
    
    # Clean the generated articles
    english_data["content"] = clean_text(english_data["content"])
    german_data["content"] = clean_text(german_data["content"])
    
    return english_data, german_data

def combine_keywords(article_keywords=None, summary_keywords=None, content_keywords=None):
    """
    Combine keywords from different sources into a single set.
    """
    combined_keywords = set()
    
    if article_keywords:
        combined_keywords.update(article_keywords)
        
    if summary_keywords:
        combined_keywords.update(summary_keywords)
        
    if content_keywords:
        combined_keywords.update(content_keywords)
        
    return list(combined_keywords)