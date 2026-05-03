"""Web search and URL fetching tools (optional — needs duckduckgo-search, beautifulsoup4)."""

from __future__ import annotations

from tool_registry import tool


@tool(
    name="web_search",
    description="Search the web using DuckDuckGo. Returns top 5 results with title, URL, and snippet.",
    parameters={
        "query": {"type": "string", "description": "Search query"},
    },
)
def web_search(query: str) -> str:
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        return "ERROR: duckduckgo-search not installed. Run: pip install duckduckgo-search"

    try:
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=5):
                results.append(f"**{r['title']}**\n{r['href']}\n{r['body']}\n")
        if not results:
            return "No results found."
        return "\n".join(results)
    except Exception as exc:
        return f"ERROR: Search failed: {exc}"


@tool(
    name="fetch_url",
    description="Fetch a web page and extract its text content.",
    parameters={
        "url": {"type": "string", "description": "URL to fetch"},
    },
)
def fetch_url(url: str) -> str:
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError:
        return "ERROR: requests and beautifulsoup4 required. Run: pip install requests beautifulsoup4"

    # Basic URL validation
    if not url.startswith(("http://", "https://")):
        return "ERROR: URL must start with http:// or https://"

    try:
        resp = requests.get(url, timeout=15, headers={"User-Agent": "GemmaAgent/1.0"})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Remove scripts, styles
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)
        # Truncate
        max_chars = 8000
        if len(text) > max_chars:
            text = text[:max_chars] + "\n... (truncated)"
        return text
    except Exception as exc:
        return f"ERROR: Failed to fetch URL: {exc}"
