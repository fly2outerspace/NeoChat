"""Web search tool using DuckDuckGo search engine."""
import asyncio
from typing import List, Optional

import requests
from bs4 import BeautifulSoup
from ddgs import DDGS
from pydantic import BaseModel, Field

from app.logger import logger
from app.tool.base import BaseTool, ToolResult
from app.utils.enums import ToolName


class SearchItem(BaseModel):
    """Represents a single search result item."""

    title: str = Field(description="The title of the search result")
    url: str = Field(description="The URL of the search result")
    description: Optional[str] = Field(
        default=None, description="A description or snippet of the search result"
    )

    def __str__(self) -> str:
        """String representation of a search result item."""
        return f"{self.title} - {self.url}"


class WebSearchEngine(BaseModel):
    """Base class for web search engines."""

    model_config = {"arbitrary_types_allowed": True}

    def perform_search(
        self, query: str, num_results: int = 10, *args, **kwargs
    ) -> List[SearchItem]:
        """
        Perform a web search and return a list of search items.

        Args:
            query (str): The search query to submit to the search engine.
            num_results (int, optional): The number of search results to return. Default is 10.
            args: Additional arguments.
            kwargs: Additional keyword arguments.

        Returns:
            List[SearchItem]: A list of SearchItem objects matching the search query.
        """
        raise NotImplementedError


class DuckDuckGoSearchEngine(WebSearchEngine):
    """DuckDuckGo search engine implementation."""

    def perform_search(
        self, query: str, num_results: int = 10, *args, **kwargs
    ) -> List[SearchItem]:
        """
        DuckDuckGo search engine.

        Returns results formatted according to SearchItem model.
        """
        try:
            with DDGS() as ddgs:
                raw_results = list(ddgs.text(query, max_results=num_results))
                logger.debug(f"DuckDuckGo search returned {len(raw_results)} raw results")

            if not raw_results:
                logger.warning(f"No results returned from DuckDuckGo search for query: {query}")
                return []

            results = []
            for i, item in enumerate(raw_results):
                try:
                    # DuckDuckGo search returns dict with keys: title, body, href
                    if isinstance(item, dict):
                        title = item.get("title", "") or f"Result {i+1}"
                        url = item.get("href", "") or item.get("url", "")
                        description = item.get("body", "") or item.get("description", "") or ""
                        
                        results.append(
                            SearchItem(
                                title=title,
                                url=url,
                                description=description
                            )
                        )
                    else:
                        # Fallback for unexpected types
                        logger.warning(f"Unexpected result type: {type(item)}")
                        continue

                except Exception as e:
                    logger.warning(f"Error processing search result item {i}: {e}, item type: {type(item)}")
                    continue

            logger.info(f"Successfully processed {len(results)} search results")
            return results

        except Exception as e:
            logger.error(f"Error in DuckDuckGoSearchEngine.perform_search: {e}", exc_info=True)
            # Return empty list instead of raising to allow fallback mechanisms
            return []


class SearchResult(BaseModel):
    """Represents a single search result."""

    position: int = Field(description="Position in search results")
    url: str = Field(description="URL of the search result")
    title: str = Field(default="", description="Title of the search result")
    description: str = Field(
        default="", description="Description or snippet of the search result"
    )
    raw_content: Optional[str] = Field(
        default=None, description="Raw content from the search result page if available"
    )

    def __str__(self) -> str:
        """String representation of a search result."""
        return f"{self.title} ({self.url})"


class WebContentFetcher:
    """Utility class for fetching web content."""

    @staticmethod
    async def fetch_content(url: str, timeout: int = 10) -> Optional[str]:
        """
        Fetch and extract the main content from a webpage.

        Args:
            url: The URL to fetch content from
            timeout: Request timeout in seconds

        Returns:
            Extracted text content or None if fetching fails
        """
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

        try:
            # Use asyncio to run requests in a thread pool
            response = await asyncio.get_event_loop().run_in_executor(
                None, lambda: requests.get(url, headers=headers, timeout=timeout)
            )

            if response.status_code != 200:
                logger.warning(
                    f"Failed to fetch content from {url}: HTTP {response.status_code}"
                )
                return None

            # Parse HTML with BeautifulSoup
            soup = BeautifulSoup(response.text, "html.parser")

            # Remove script and style elements
            for script in soup(["script", "style", "header", "footer", "nav"]):
                script.extract()

            # Get text content
            text = soup.get_text(separator="\n", strip=True)

            # Clean up whitespace and limit size (10KB max)
            text = " ".join(text.split())
            return text[:10000] if text else None

        except Exception as e:
            logger.warning(f"Error fetching content from {url}: {e}")
            return None


_WEB_SEARCH_DESCRIPTION = """Search the web for real-time information about any topic using DuckDuckGo search.
This tool returns comprehensive search results with relevant information, URLs, titles, and descriptions.
Optionally, you can fetch the full content from result pages for more detailed information."""


class WebSearch(BaseTool):
    """Search the web for information using DuckDuckGo search engine."""

    name: str = ToolName.WEB_SEARCH
    description: str = _WEB_SEARCH_DESCRIPTION
    parameters: dict = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "(required) The search query to submit to DuckDuckGo search engine.",
            },
            "num_results": {
                "type": "integer",
                "description": "(optional) The number of search results to return. Default is 5.",
                "default": 5,
            },
            "fetch_content": {
                "type": "boolean",
                "description": "(optional) Whether to fetch full content from result pages. Default is false.",
                "default": False,
            },
        },
        "required": ["query"],
    }

    _search_engine: DuckDuckGoSearchEngine = DuckDuckGoSearchEngine()
    _content_fetcher: WebContentFetcher = WebContentFetcher()

    async def execute(
        self,
        query: str,
        num_results: int = 5,
        fetch_content: bool = False,
        **kwargs,
    ) -> ToolResult:
        """
        Execute a web search and return detailed search results.

        Args:
            query: The search query to submit to DuckDuckGo search engine
            num_results: The number of search results to return (default: 5)
            fetch_content: Whether to fetch content from result pages (default: False)

        Returns:
            A ToolResult containing formatted search results
        """
        try:
            logger.info(f"Searching DuckDuckGo for: {query}")

            # Perform search using DuckDuckGoSearchEngine
            search_items = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._search_engine.perform_search(query, num_results=num_results),
            )

            logger.debug(f"Received {len(search_items) if search_items else 0} search items")

            if not search_items:
                logger.warning(f"No search results found for query: {query}")
                return ToolResult(
                    error=f"No search results found for query: {query}. This might be due to network issues, DuckDuckGo rate limiting, or the search query returning no results.",
                )

            # Transform search items into structured results
            results = []
            for i, item in enumerate(search_items):
                # Handle both dict and SearchItem objects
                if isinstance(item, dict):
                    results.append(
                        SearchResult(
                            position=i + 1,
                            url=item.get("url", ""),
                            title=item.get("title", f"Result {i+1}"),
                            description=item.get("description", ""),
                        )
                    )
                else:
                    # SearchItem object
                    results.append(
                        SearchResult(
                            position=i + 1,
                            url=item.url,
                            title=item.title or f"Result {i+1}",
                            description=item.description or "",
                        )
                    )

            # Fetch content if requested
            if fetch_content:
                results = await self._fetch_content_for_results(results)

            # Format output
            output = self._format_results(query, results)

            return ToolResult(content=output)

        except Exception as e:
            logger.error(f"Error during web search: {e}", exc_info=True)
            return ToolResult(
                error=f"Failed to perform web search: {str(e)}. Please check your network connection and ensure the duckduckgo-search library is properly installed.",
            )

    async def _fetch_content_for_results(
        self, results: List[SearchResult]
    ) -> List[SearchResult]:
        """Fetch and add web content to search results."""
        if not results:
            return []

        # Create tasks for each result
        tasks = [self._fetch_single_result_content(result) for result in results]

        # Execute all fetch tasks concurrently
        fetched_results = await asyncio.gather(*tasks)

        return list(fetched_results)

    async def _fetch_single_result_content(self, result: SearchResult) -> SearchResult:
        """Fetch content for a single search result."""
        if result.url:
            content = await self._content_fetcher.fetch_content(result.url)
            if content:
                result.raw_content = content
        return result

    def _format_results(self, query: str, results: List[SearchResult]) -> str:
        """Format search results into a readable string."""
        result_text = [f"Search results for '{query}':"]

        for result in results:
            # Add title with position number
            title = result.title.strip() or "No title"
            result_text.append(f"\n{result.position}. {title}")

            # Add URL with proper indentation
            result_text.append(f"   URL: {result.url}")

            # Add description if available
            if result.description.strip():
                result_text.append(f"   Description: {result.description}")

            # Add content preview if available
            if result.raw_content:
                content_preview = result.raw_content[:1000].replace("\n", " ").strip()
                if len(result.raw_content) > 1000:
                    content_preview += "..."
                result_text.append(f"   Content: {content_preview}")

        result_text.append(f"\nTotal results: {len(results)}")

        return "\n".join(result_text)


