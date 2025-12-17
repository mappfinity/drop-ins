import wikipedia
from langchain.tools import tool
from typing import List, Dict, Any, Optional


#----------------------------------------------------------------
# WIKIPEDIA SEARCH
#----------------------------------------------------------------
@tool
def search_wikipedia(query: str) -> str:
    """Search Wikipedia for reliable, encyclopedic information on any topic.
    
    Use this tool when you need factual information about established topics including
    people, places, events, concepts, organizations, or any subject with encyclopedic 
    coverage. Best for well-known topics rather than very recent events or niche subjects.
    
    Args:
        query: The topic or subject to search for (e.g., "Albert Einstein", "photosynthesis")
    
    Returns:
        Summaries from up to 3 relevant Wikipedia articles, or a message if no results found.
    """
    page_titles = wikipedia.search(query)
    summaries = []
    for page_title in page_titles[:3]:
        try:
            wiki_page = wikipedia.page(title=page_title, auto_suggest=False)
            summaries.append(f"Page: {page_title}\nSummary: {wiki_page.summary}")
        except (
            wikipedia.exceptions.PageError,
            wikipedia.exceptions.DisambiguationError,
        ):
            pass
    if not summaries:
        return "No good Wikipedia Search Result was found"
    return "\n\n".join(summaries)


#----------------------------------------------------------------
# TAVILY WEB SEARCH (API KEY NEEDED)
#----------------------------------------------------------------

from typing import List, Dict, Any
import logging
import os
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

_REQUEST_TIMEOUT = int(os.getenv("WEBRETRIEVERS_TIMEOUT", "25"))
_MAX_RETRIES = int(os.getenv("WEBRETRIEVERS_RETRIES", "3"))


def _make_session(retries: int = _MAX_RETRIES, backoff: float = 0.3) -> requests.Session:
    """Create a requests session with retry logic."""
    s = requests.Session()
    retry = Retry(total=retries, backoff_factor=backoff, status_forcelist=(429, 500, 502, 503, 504))
    adapter = HTTPAdapter(max_retries=retry)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s

@tool
def retrieve_tavily(query: str, max_results: int = 3) -> List[Dict[str, Any]]:
    """Search the web for current information and real-time content using Tavily.
    
    Use this tool when you need up-to-date information from across the web, including
    recent events, news, current data, or topics that require fresh sources. Better
    suited for time-sensitive queries than encyclopedic sources like Wikipedia.
    
    Args:
        query: The search query string
        max_results: Maximum number of results to return (default: 3)
    
    Returns:
        List of search results, each containing 'text' (content snippet) and 'meta' 
        (metadata with url, title, source, score, and timestamp). Returns empty list
        if search fails or no results found.
    """

    
    results: List[Dict[str, Any]] = []
    
    if not query:
        return results

    #Tavily is disabled unless TAVILY_API_KEY env var is defined.
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return results

    tavily_endpoint = os.getenv("TAVILY_ENDPOINT", "https://api.tavily.com/search")
    headers = {"Content-Type": "application/json"}
    payload = {
        "api_key": api_key,
        "query": query,
        "max_results": max_results,
        "search_depth": "basic",
        "include_answer": False,
        "include_images": False,
        "include_raw_content": False,
    }

    try:
        sess = _make_session()
        r = sess.post(tavily_endpoint, json=payload, headers=headers, timeout=_REQUEST_TIMEOUT)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        logger.warning("web_retrievers: Tavily request failed: %s", e)
        return results

    items = data.get("results") or []
    for it in items[:max_results]:
        if not isinstance(it, dict):
            continue
        text = it.get("content") or it.get("text") or it.get("snippet") or ""
        meta: Dict[str, Any] = {
            "source": "tavily",
            "retrieved_at": time.time(),
            "url": it.get("url"),
            "title": it.get("title"),
        }
        if "score" in it:
            try:
                meta["score"] = float(it.get("score"))
            except Exception:
                meta["score"] = None
        existing_meta = it.get("metadata") or {}
        if isinstance(existing_meta, dict):
            for k, v in existing_meta.items():
                if k not in meta:
                    meta[k] = v
        results.append({"text": text, "meta": meta})

    return results