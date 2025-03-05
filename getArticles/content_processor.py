"""
Process article content for the news fetching pipeline.
"""
import os
import asyncio
import logging
from typing import Dict, Any, Optional, List

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ContentProcessor:
    """Process article content including summarization and embeddings."""
    
    def __init__(self, llm_choice="openai"):
        """
        Initialize the content processor.
        
        Args:
            llm_choice: The LLM provider to use ("openai" or "gemini")
        """
        self.llm_choice = llm_choice
        self.openai_client = None
        
        # Initialize the chosen LLM
        self._initialize_llm()
        
    def _initialize_llm(self):
        """Initialize the language model based on the chosen provider."""
        try:
            if self.llm_choice == "openai":
                from openai import OpenAI
                api_key = os.getenv("OPENAI_API_KEY")
                if not api_key:
                    logger.error("OpenAI API key not found in environment variables")
                    return
                    
                self.openai_client = OpenAI(api_key=api_key)
                logger.info("OpenAI client initialized successfully")
                
            elif self.llm_choice == "gemini":
                import google.generativeai as genai
                api_key = os.getenv("GEMINI_API_KEY")
                if not api_key:
                    logger.error("Gemini API key not found in environment variables")
                    return
                    
                genai.configure(api_key=api_key)
                self.genai_client = genai
                logger.info("Gemini client initialized successfully")
                
            else:
                logger.error(f"Unsupported LLM choice: {self.llm_choice}")
                
        except ImportError as e:
            logger.error(f"Failed to import required libraries: {e}")
        except Exception as e:
            logger.error(f"Error initializing LLM: {e}")
    
    async def generate_summary(self, article_url: str, article_headline: str) -> Optional[str]:
        """
        Generate a summary of the article.
        
        Args:
            article_url: The URL of the article
            article_headline: The headline of the article
            
        Returns:
            A summary of the article or None if generation fails
        """
        if not article_headline:
            logger.warning("No headline provided for summarization")
            return None
            
        prompt = f"""Summarize the article with headline: "{article_headline}"
URL: {article_url}
Provide a brief, informative summary in 2-3 sentences."""

        try:
            if self.llm_choice == "openai" and self.openai_client:
                # Use asyncio.to_thread to make the synchronous OpenAI API call non-blocking
                response = await asyncio.to_thread(
                    self.openai_client.chat.completions.create,
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.5,
                    max_tokens=150
                )
                return response.choices[0].message.content.strip()
                
            elif self.llm_choice == "gemini" and hasattr(self, "genai_client"):
                # Implement Gemini summarization here
                pass
                
            logger.warning("No valid LLM client available for summarization")
            return None
            
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            return None
    
    async def generate_embedding(self, text: str) -> Optional[List[float]]:
        """
        Generate an embedding vector for the given text.
        
        Args:
            text: The text to generate an embedding for
            
        Returns:
            An embedding vector or None if generation fails
        """
        if not text:
            logger.warning("No text provided for embedding generation")
            return None
            
        try:
            if self.llm_choice == "openai" and self.openai_client:
                response = await asyncio.to_thread(
                    self.openai_client.embeddings.create,
                    model="text-embedding-ada-002",
                    input=text
                )
                return response.data[0].embedding
                
            logger.warning("No valid LLM client available for embedding generation")
            return None
            
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            return None
    
    async def enrich_article(self, article: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enrich an article with summary and embedding.
        
        Args:
            article: Article data dictionary
            
        Returns:
            Enriched article data dictionary
        """
        if not article:
            return article
            
        try:
            headline = article.get('headline', '')
            url = article.get('url', '')
            
            if headline and url:
                # Generate summary
                summary = await self.generate_summary(url, headline)
                if summary:
                    article['summary'] = summary
                    
                    # Generate embedding from summary
                    embedding = await self.generate_embedding(summary)
                    if embedding:
                        article['embedding'] = embedding
            
        except Exception as e:
            logger.error(f"Error enriching article: {e}")
            
        return article
    
    async def enrich_articles(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Enrich multiple articles with summaries and embeddings.
        
        Args:
            articles: List of article data dictionaries
            
        Returns:
            List of enriched article data dictionaries
        """
        enriched_articles = []
        
        for article in articles:
            enriched_article = await self.enrich_article(article)
            enriched_articles.append(enriched_article)
            
        return enriched_articles