import os
import logging
import time
from tavily import TavilyClient

logger = logging.getLogger(__name__)

RESEARCH_BATCH_SIZE = 5
TAVILY_SEARCH_DEPTH = "advanced"
MAX_RESULTS_PER_PLACE = 5


def get_tavily_client():
    """Initialize and return Tavily clients."""
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        raise ValueError("TAVILY_API_KEY not set in environment")
    return TavilyClient(api_key=api_key)


def build_general_query(place: dict, location_name: str, original_query: str) -> str:
    """
    Build a general review search query.
    No site: operators — Tavily handles domain filtering via include_domains.
    """
    name = place["name"]
    city = location_name.split(",")[0].strip() if "," in location_name else location_name
    cuisine = place.get("cuisine", "")
    amenity = place.get("amenity", "place")

    base = f'"{name}" {city}'
    if cuisine:
        base += f" {cuisine}"

    if amenity in ("restaurant", "fast_food", "cafe"):
        angle = "review what to order best dishes"
    elif amenity in ("bar", "pub", "nightclub", "brewery"):
        angle = "review cocktails atmosphere worth visiting"
    elif amenity in ("museum", "gallery"):
        angle = "review worth visiting highlights"
    elif amenity == "park":
        angle = "review trail experience visit"
    elif amenity == "hotel":
        angle = "review stay experience"
    else:
        angle = "review experience worth visiting"

    return f"{base} {angle} 2024 2025"


def build_reddit_query(place: dict, location_name: str, original_query: str) -> str:
    """
    Build a Reddit-targeted search query.
    Kept conversational — Reddit users ask questions and share opinions naturally.
    """
    name = place["name"]
    city = location_name.split(",")[0].strip() if "," in location_name else location_name
    return f"{name} {city} recommendations thoughts review"

def classify_source(url: str) -> str:
    """Classify a URL into a source type category."""
    u = url.lower()
    if "reddit.com" in u:       return "reddit"
    if "yelp.com" in u:         return "yelp"
    if "tripadvisor.com" in u:  return "tripadvisor"
    if "google.com" in u:       return "google"
    if "alltrails.com" in u:    return "alltrails"
    if "timeout.com" in u:      return "editorial"
    if "eater.com" in u:        return "editorial"
    if "thrillist.com" in u:    return "editorial"
    if any(b in u for b in ["blog", "wordpress", "medium", "substack"]):
        return "blog"
    return "web"


def calculate_research_score(results: list[dict]) -> float:
    """Composite quality score: Tavily relevance + source diversity bonuses."""
    if not results:
        return 0.0

    avg_score = sum(r.get("score", 0) for r in results) / len(results)
    source_types = {r.get("source_type") for r in results}

    diversity_bonus  = len(source_types) * 0.10
    reddit_bonus     = 0.20 if "reddit"    in source_types else 0.0
    editorial_bonus  = 0.12 if "editorial" in source_types else 0.0
    yelp_bonus       = 0.08 if "yelp"      in source_types else 0.0

    return round(min(avg_score + diversity_bonus + reddit_bonus + editorial_bonus + yelp_bonus, 1.0), 3)

def research_single_place(
    tavily: TavilyClient,
    place: dict,
    location_name: str,
    original_query: str
) -> dict:
    """
    Research a single place with two focused Tavily searches:
      Pass 1 — General: Yelp, TripAdvisor, travel blogs, editorial
      Pass 2 — Reddit only: community opinions and firsthand experiences

    Using Tavily's include_domains parameter (the correct API approach —
    NOT site: operators in the query string which Tavily ignores).
    """
    name = place["name"]
    research_results = []
    sentiment_snippets = []
    sources = []
    reddit_snippets = []

    general_query = build_general_query(place, location_name, original_query)
    reddit_query  = build_reddit_query(place, location_name, original_query)

    try:
        logger.info(f"[General] '{name}' → {general_query[:80]}...")
        result = tavily.search(
            query=general_query,
            search_depth=TAVILY_SEARCH_DEPTH,
            max_results=MAX_RESULTS_PER_PLACE,
            include_answer=True,
            include_raw_content=False,
            include_domains=["yelp.com", "tripadvisor.com", "timeout.com",
                             "eater.com", "thrillist.com", "alltrails.com"],
        )

        if result.get("answer"):
            sentiment_snippets.append(result["answer"])

        for item in result.get("results", []):
            url = item.get("url", "")
            content = item.get("content", "")
            research_results.append({
                "title":       item.get("title", ""),
                "url":         url,
                "snippet":     content[:500],
                "score":       item.get("score", 0),
                "source_type": classify_source(url),
            })
            sources.append(url)
            if content:
                sentiment_snippets.append(content[:300])

        time.sleep(0.4)

    except Exception as e:
        logger.error(f"General research failed for '{name}': {e}")

    # ── Pass 2: Reddit-only ───────────────────────────────────────────────
    try:
        logger.info(f"[Reddit]  '{name}' → {reddit_query[:80]}...")
        reddit_result = tavily.search(
            query=reddit_query,
            search_depth="basic",             # basic is enough for Reddit threads
            max_results=5,
            include_answer=False,
            include_raw_content=False,
            include_domains=["reddit.com"],   # ← correct Tavily API param
        )

        for item in reddit_result.get("results", []):
            url = item.get("url", "")
            content = item.get("content", "")
            if url and "reddit.com" in url:
                research_results.append({
                    "title":       item.get("title", ""),
                    "url":         url,
                    "snippet":     content[:500],
                    "score":       item.get("score", 0),
                    "source_type": "reddit",
                })
                sources.append(url)
                if content:
                    reddit_snippets.append(content[:600])

        time.sleep(0.4)

    except Exception as e:
        logger.error(f"Reddit research failed for '{name}': {e}")

    all_snippets = sentiment_snippets[:4] + reddit_snippets[:2]
    combined_text = " | ".join(all_snippets) if all_snippets else "No reviews found."

    has_reddit = any("reddit.com" in s for s in sources)
    
    # Calculate web summary separate from reddit summary
    web_snippets = sentiment_snippets[:5]
    web_summary_text = " | ".join(web_snippets) if web_snippets else "No reviews found."

    return {
        **place,
        "research_results":  research_results,
        "research_summary":  combined_text[:1500],
        "web_summary":       web_summary_text[:1500],
        "reddit_summary":    " | ".join(reddit_snippets[:4]) if reddit_snippets else "",
        "sources":           list(dict.fromkeys(sources))[:6], 
        "source_count":      len(research_results),
        "has_reddit":        has_reddit,
        "has_blog":          any(classify_source(s) == "blog" for s in sources),
        "research_score":    calculate_research_score(research_results),
    }


def run_research_agent(state: dict) -> dict:

    if state.get("discovery_status") not in ["success"]:
        return {
            **state,
            "research_status": "failed",
            "error": state.get("error", "Discovery failed, cannot research places")
        }

    places = state.get("discovered_places", [])
    if not places:
        return {
            **state,
            "research_status": "no_places",
            "error": "No places were discovered to research"
        }

    location_name  = state.get("location_name", "")
    original_query = state.get("query", "")

    candidates = places[:RESEARCH_BATCH_SIZE]
    logger.info(f"Researching {len(candidates)} places (2-pass: general + Reddit)...")

    try:
        tavily = get_tavily_client()
    except ValueError as e:
        logger.error(str(e))
        return {**state, "research_status": "failed", "error": str(e)}

    researched_places = []
    for i, place in enumerate(candidates):
        logger.info(f"[{i+1}/{len(candidates)}] {place['name']}")
        enriched = research_single_place(tavily, place, location_name, original_query)
        researched_places.append(enriched)

    researched_places.sort(key=lambda x: x.get("research_score", 0), reverse=True)

    return {
        **state,
        "researched_places": researched_places,
        "research_status":   "success",
        "research_count":    len(researched_places),
    }
