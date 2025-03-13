"""
Module for defining and checking news sources.
"""

# Define news sources that will be treated as official news sources
# Articles from these sources will go through the similarity check
# and will have isNews=True
NEWS_SOURCES = [
    'espn.com',
    'nfl.com',
    'foxsports.com',
    # Enable more sources as needed
]

def is_news_source(url: str) -> bool:
    """
    Check if the given URL is from an official news source.
    
    Args:
        url: The URL to check
        
    Returns:
        True if the URL is from an official news source, False otherwise
    """
    if not url:
        return False
        
    url = url.lower()
    for source in NEWS_SOURCES:
        if source.lower() in url:
            return True
            
    return False