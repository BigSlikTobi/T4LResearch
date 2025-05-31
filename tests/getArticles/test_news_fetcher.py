import pytest
import asyncio
from unittest.mock import patch, AsyncMock
import json

from getArticles.news_fetcher import get_default_sources, fetch_news, NewsItem, fetch_from_all_sources

# Tests for get_default_sources
def test_get_default_sources():
    """
    Tests the get_default_sources function.
    """
    sources = get_default_sources()
    assert isinstance(sources, list), "Should return a list"
    assert len(sources) > 0, "Should not be an empty list"
    for source in sources:
        assert isinstance(source, dict), "Each item should be a dictionary"
        assert "name" in source, "Each source should have a 'name' key"
        assert "url" in source, "Each source should have a 'url' key"
        assert "base_url" in source, "Each source should have a 'base_url' key"
        assert "execute" in source, "Each source should have an 'execute' key"
        assert callable(source["execute"]), "The 'execute' value should be a callable"

# Scaffolding for fetch_news tests
@pytest.mark.asyncio
@patch('getArticles.news_fetcher.AsyncWebCrawler')
async def test_fetch_news_successful_extraction(MockAsyncWebCrawler):
    """
    Tests successful news extraction from a single source using fetch_news.
    """
    mock_items_data = [
        {
            "id": "Test Headline 1", # Raw headline for slugification
            "source": "test.com",
            "headline": "Test Headline 1",
            "href": "/news/article1",
            "published_at": "2023-01-01",
        },
        {
            "id": "Another Story!", # Raw headline for slugification
            "source": "test.com",
            "headline": "Another Story",
            "href": "http://external.com/news/article2", # Absolute URL
            "published_at": "2023-01-02",
        }
    ]
    mock_json_output = json.dumps(mock_items_data)

    # Configure the mock crawler instance
    mock_crawler_instance = MockAsyncWebCrawler.return_value
    mock_crawler_instance.arun = AsyncMock(return_value=mock_crawler_instance) # arun returns self
    mock_crawler_instance.extracted_content = mock_json_output

    # Call fetch_news
    news_items = await fetch_news(
        url="http://test.com/news",
        base_url="http://test.com",
        provider="test_provider",
        api_token="test_token"
    )

    # Assertions
    assert len(news_items) == 2, "Should return two news items"

    # First item assertions
    item1 = news_items[0]
    assert item1["id"] == "test-headline-1"
    assert item1["url"] == "http://test.com/news/article1"
    assert item1["source"] == "test.com"
    assert item1["headline"] == "Test Headline 1"
    assert item1["published_at"] == "2023-01-01"
    assert item1["isProcessed"] is False

    # Second item assertions
    item2 = news_items[1]
    assert item2["id"] == "another-story"
    assert item2["url"] == "http://external.com/news/article2"
    assert item2["source"] == "test.com"
    assert item2["headline"] == "Another Story"
    assert item2["published_at"] == "2023-01-02"
    assert item2["isProcessed"] is False

    # Verify that AsyncWebCrawler was called correctly
    MockAsyncWebCrawler.assert_called_once()
    # We can add more specific assertions about how AsyncWebCrawler was called if needed,
    # e.g. checking the strategy_config, but the problem implies LLMExtractionStrategy
    # does not need explicit mocking if arun is correctly mocked.
    # The important part is that arun was called, and its output was processed.
    mock_crawler_instance.arun.assert_called_once()

@pytest.mark.asyncio
@patch('getArticles.news_fetcher.AsyncWebCrawler')
async def test_fetch_news_empty_content(MockAsyncWebCrawler):
    """
    Tests fetch_news when the crawler returns empty content.
    """
    mock_crawler_instance = MockAsyncWebCrawler.return_value
    mock_crawler_instance.arun = AsyncMock(return_value=mock_crawler_instance)
    mock_crawler_instance.extracted_content = None

    news_items = await fetch_news(
        url="http://test.com/news",
        base_url="http://test.com",
        provider="test_provider",
        api_token="test_token"
    )
    assert news_items == []

@pytest.mark.asyncio
@patch('getArticles.news_fetcher.AsyncWebCrawler')
async def test_fetch_news_invalid_json(MockAsyncWebCrawler):
    """
    Tests fetch_news when the crawler returns invalid JSON content.
    """
    mock_crawler_instance = MockAsyncWebCrawler.return_value
    mock_crawler_instance.arun = AsyncMock(return_value=mock_crawler_instance)
    mock_crawler_instance.extracted_content = "<html><body>Not JSON</body></html>"

    news_items = await fetch_news(
        url="http://test.com/news",
        base_url="http://test.com",
        provider="test_provider",
        api_token="test_token"
    )
    assert news_items == []

@pytest.mark.asyncio
@patch('getArticles.news_fetcher.AsyncWebCrawler')
async def test_fetch_news_non_list_json_as_dict(MockAsyncWebCrawler):
    """
    Tests fetch_news when the crawler returns a single JSON object (not a list).
    """
    mock_item_data = {
        "id": "Single Item",
        "source": "test.com",
        "headline": "Single Item Headline",
        "href": "/news/single",
        "published_at": "2023-01-03",
    }
    mock_json_output = json.dumps(mock_item_data)

    mock_crawler_instance = MockAsyncWebCrawler.return_value
    mock_crawler_instance.arun = AsyncMock(return_value=mock_crawler_instance)
    mock_crawler_instance.extracted_content = mock_json_output

    news_items = await fetch_news(
        url="http://test.com/news", # This URL is for the crawler
        base_url="http://test.com", # This is used for resolving relative hrefs
        provider="test_provider",
        api_token="test_token"
    )

    assert len(news_items) == 1
    item = news_items[0]
    assert item["id"] == "single-item"
    assert item["url"] == "http://test.com/news/single"
    assert item["source"] == "test.com"
    assert item["headline"] == "Single Item Headline"
    assert item["published_at"] == "2023-01-03"
    assert item["isProcessed"] is False

@pytest.mark.asyncio
@patch('getArticles.news_fetcher.AsyncWebCrawler')
async def test_fetch_news_crawler_arun_raises_exception(MockAsyncWebCrawler):
    """
    Tests fetch_news when the crawler's arun method raises an exception.
    """
    mock_crawler_instance = MockAsyncWebCrawler.return_value
    mock_crawler_instance.arun = AsyncMock(side_effect=Exception("Crawler network error"))

    news_items = await fetch_news(
        url="http://test.com/news",
        base_url="http://test.com",
        provider="test_provider",
        api_token="test_token"
    )
    assert news_items == []

@pytest.mark.asyncio
@patch('getArticles.news_fetcher.fetch_news', new_callable=AsyncMock)
async def test_fetch_from_all_sources_basic(mocked_fetch_news):
    """
    Tests fetch_from_all_sources with multiple successful sources.
    """
    mock_sources = [
        {"name": "source1", "url": "http://s1.com/news", "base_url": "http://s1.com", "execute": True},
        {"name": "source2", "url": "http://s2.com/news", "base_url": "http://s2.com", "execute": True},
    ]

    async def fetch_news_side_effect(url, base_url, provider, api_token, **kwargs):
        if url == "http://s1.com/news":
            return [{"id": "s1_item1", "headline": "S1H1", "href": "/a1", "url": "http://s1.com/a1", "source": "s1_initial_source", "published_at": "2023-01-01", "isProcessed": False}]
        elif url == "http://s2.com/news":
            return [{"id": "s2_item1", "headline": "S2H1", "href": "/b1", "url": "http://s2.com/b1", "source": "s2_initial_source", "published_at": "2023-01-02", "isProcessed": False}]
        return []

    mocked_fetch_news.side_effect = fetch_news_side_effect

    all_items = await fetch_from_all_sources(mock_sources, "test_provider", "test_token")

    assert len(all_items) == 2
    assert mocked_fetch_news.call_count == 2

    # Check item from source1
    item1 = next(item for item in all_items if item["id"] == "s1_item1")
    assert item1["source"] == "source1" # Overridden
    assert item1["headline"] == "S1H1"

    # Check item from source2
    item2 = next(item for item in all_items if item["id"] == "s2_item1")
    assert item2["source"] == "source2" # Overridden
    assert item2["headline"] == "S2H1"


@pytest.mark.asyncio
@patch('getArticles.news_fetcher.fetch_news', new_callable=AsyncMock)
async def test_fetch_from_all_sources_one_source_fails(mocked_fetch_news):
    """
    Tests fetch_from_all_sources when one source fails to return items.
    """
    mock_sources = [
        {"name": "source1", "url": "http://s1.com/news", "base_url": "http://s1.com", "execute": True},
        {"name": "source2", "url": "http://s2.com/news", "base_url": "http://s2.com", "execute": True}, # This one will fail
    ]

    async def fetch_news_side_effect(url, base_url, provider, api_token, **kwargs):
        if url == "http://s1.com/news":
            return [{"id": "s1_item1", "headline": "S1H1", "href": "/a1", "url": "http://s1.com/a1", "source": "s1_initial_source", "published_at": "2023-01-01", "isProcessed": False}]
        elif url == "http://s2.com/news":
            return [] # Simulates failure or no items
        return []

    mocked_fetch_news.side_effect = fetch_news_side_effect

    all_items = await fetch_from_all_sources(mock_sources, "test_provider", "test_token")

    assert len(all_items) == 1
    assert mocked_fetch_news.call_count == 2

    item1 = all_items[0]
    assert item1["id"] == "s1_item1"
    assert item1["source"] == "source1" # Overridden
    assert item1["headline"] == "S1H1"

@pytest.mark.asyncio
@patch('getArticles.news_fetcher.fetch_news', new_callable=AsyncMock)
async def test_fetch_from_all_sources_one_source_raises_exception(mocked_fetch_news):
    """
    Tests fetch_from_all_sources when one source raises an exception during fetch.
    """
    mock_sources = [
        {"name": "source1", "url": "http://s1.com/news", "base_url": "http://s1.com", "execute": True},
        {"name": "source2", "url": "http://s2.com/news", "base_url": "http://s2.com", "execute": True}, # This one will raise
    ]

    async def fetch_news_side_effect(url, base_url, provider, api_token, **kwargs):
        if url == "http://s1.com/news":
            return [{"id": "s1_item1", "headline": "S1H1", "href": "/a1", "url": "http://s1.com/a1", "source": "s1_initial_source", "published_at": "2023-01-01", "isProcessed": False}]
        elif url == "http://s2.com/news":
            raise Exception("Simulated fetch error")
        return []

    mocked_fetch_news.side_effect = fetch_news_side_effect

    all_items = await fetch_from_all_sources(mock_sources, "test_provider", "test_token")

    assert len(all_items) == 1
    assert mocked_fetch_news.call_count == 2

    item1 = all_items[0]
    assert item1["id"] == "s1_item1"
    assert item1["source"] == "source1" # Overridden
    assert item1["headline"] == "S1H1"

@pytest.mark.asyncio
@patch('getArticles.news_fetcher.fetch_news', new_callable=AsyncMock)
async def test_fetch_from_all_sources_no_sources_execute(mocked_fetch_news):
    """
    Tests fetch_from_all_sources when no sources are marked for execution.
    """
    mock_sources = [
        {"name": "source1", "url": "http://s1.com/news", "base_url": "http://s1.com", "execute": False},
        {"name": "source2", "url": "http://s2.com/news", "base_url": "http://s2.com", "execute": False},
    ]

    all_items = await fetch_from_all_sources(mock_sources, "test_provider", "test_token")

    assert len(all_items) == 0
    assert mocked_fetch_news.call_count == 0

@pytest.mark.asyncio
@patch('getArticles.news_fetcher.fetch_news', new_callable=AsyncMock)
async def test_fetch_from_all_sources_empty_sources_list(mocked_fetch_news):
    """
    Tests fetch_from_all_sources with an empty list of sources.
    """
    all_items = await fetch_from_all_sources([], "test_provider", "test_token")

    assert len(all_items) == 0
    assert mocked_fetch_news.call_count == 0
