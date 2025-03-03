import sys
import os

# Add the parent directory to the Python path to allow for absolute imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from createArticles.getImage import search_image

async def find_article_image(content, keywords):
    """
    Search for an appropriate image for the article based on content and keywords.
    
    Args:
        content (str): The article content to use for image search
        keywords (list): Keywords to enhance the image search
        
    Returns:
        dict: Image data including URL, attribution, alt text, etc.
    """
    print("Searching for image for article content...")
    image_data = await search_image(content, keywords)
    return image_data

def use_existing_image(article):
    """
    Extract image data from an existing article.
    
    Args:
        article (dict): Existing article with image data
        
    Returns:
        dict: Image data formatted for use in new/updated articles
    """
    return {
        "image": article["imageUrl"],
        "imageAltText": article["imageAltText"],
        "url": article["imageSource"],
        "imageAttribution": article["imageAttribution"]
    }