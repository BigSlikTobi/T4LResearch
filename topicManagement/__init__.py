"""
Topic Management Package for T4LResearch.

This package handles the assignment of special topics to news articles based on content matching.
It identifies when an article's content aligns with a defined topic from the Topics table
and updates the article with the appropriate topic reference.
"""

from .topic_matcher import match_article_with_topics, process_article, process_all_articles
from .topic_fetcher import fetch_active_topics

__all__ = [
    'match_article_with_topics',
    'process_article',
    'process_all_articles',
    'fetch_active_topics'
]