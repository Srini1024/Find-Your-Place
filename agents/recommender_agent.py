

import os
import json
import logging
import google.generativeai as genai

logger = logging.getLogger(__name__)

TOP_N = 5

SYSTEM_PROMPT = """You are an expert local guide and travel writer. Your job is to analyze research data \
about local places and create compelling, honest, and useful recommendations for someone looking for places to visit.

You have access to data from Reddit discussions, travel blogs, review sites, and web research.
Your recommendations should feel like advice from a knowledgeable local friend — warm, specific, and trustworthy.

Focus on:
- What makes each place genuinely special or unique
- Real sentiment from reviews (honest positives AND any notable negatives)
- Practical tips (best dishes, peak hours, hidden gems)
- Why it ranks where it does

Format your response ONLY as a valid JSON array with exactly {top_n} objects.
Each object must have these exact keys:
{{
  "rank": 1,
  "name": "Place Name",
  "tagline": "A compelling one-liner about this place",
  "why_visit": "2-3 sentences on what makes it special and why you're recommending it",
  "highlights": ["bullet 1", "bullet 2", "bullet 3"],
  "web_says": "Provide a 5-line summary of the general web consensus (blogs, Yelp, TripAdvisor). Mention specific recurring praise or common complaints found in the research data.",
  "reddit_says": "Write a conversational 5-line summary of Reddit discussions. Start with phrases like 'Reddit users rave about...' or 'According to local subreddits...'. Include at least 3 specific mentions of dishes, deals, or 'insider' opinions found in the threads.",
  "best_for": "e.g. 'Date nights, craft beer enthusiasts, groups'",
  "insider_tip": "A specific practical tip based on the research data",
  "distance": "X.X km away",
  "address": "address string or empty",
  "website": "url or empty",
  "category": "restaurant/bar/cafe/etc"
}}

Return ONLY the JSON array. No markdown, no explanation, no code blocks."""


def build_recommendation_prompt(
    places: list[dict],
    query: str,
    location_name: str,
    top_n: int = TOP_N
) -> str:
    """
    Build the LLM prompt with all research data about candidate places.
    """
    place_summaries = []
    for i, place in enumerate(places):
        reddit_summary = place.get("reddit_summary", "")
        summary = f"""
--- Place {i+1}: {place['name']} ---
Category: {place.get('amenity', 'Unknown')}
Distance: {place.get('distance_km', 'Unknown')} km
Address: {place.get('address', 'Not available')}
Website: {place.get('website', 'None')}
Phone: {place.get('phone', 'Not listed')}
Opening Hours: {place.get('opening_hours', 'Not listed')}
Research Score: {place.get('research_score', 0):.2f}
Sources Found: {place.get('source_count', 0)} ({', '.join(set(r.get('source_type','') for r in place.get('research_results', [])))})
Web Summary: {place.get('web_summary', 'No web data available')}
Reddit Summary: {reddit_summary if reddit_summary else 'No Reddit data found'}
Research Summary: {place.get('research_summary', 'No research data available')}
"""
        place_summaries.append(summary)

    user_prompt = f"""User is looking for: "{query}"
Location: {location_name}

I have researched {len(places)} candidate places. Based on the research data below, \
create the Top {top_n} recommendations. Prioritize places with strong positive reviews, \
authentic community endorsement, and that best match what the user is looking for.

{chr(10).join(place_summaries)}

Now provide the Top {top_n} recommendations as a JSON array:"""

    return user_prompt


def run_recommender_agent(state: dict) -> dict:
    
    if state.get("research_status") not in ["success"]:
        places = state.get("discovered_places", [])
        if not places:
            return {
                **state,
                "recommender_status": "failed",
                "error": state.get("error", "Research failed, cannot generate recommendations")
            }   
        state = {**state, "researched_places": places, "research_status": "fallback"}

    places = state.get("researched_places", [])
    if not places:
        return {
            **state,
            "recommender_status": "failed",
            "error": "No researched places available"
        }

    query = state.get("query", "places to visit")
    location_name = state.get("location_name", "your area")

    candidates = places[:8]

    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        logger.warning("No Gemini API key found, using simple ranking fallback")
        return build_fallback_recommendations(state, candidates, query, location_name)

    import time as _time
    try:
        genai.configure(api_key=gemini_key)
        
        system_msg = SYSTEM_PROMPT.format(top_n=min(TOP_N, len(candidates)))
        user_msg = build_recommendation_prompt(candidates, query, location_name, min(TOP_N, len(candidates)))
        
        generation_config = {
            "temperature": 0.7,
            "max_output_tokens": 3000,
        }
        
        model = genai.GenerativeModel(
            model_name="models/gemini-2.5-flash",
            generation_config=generation_config,
            system_instruction=system_msg
        )

        logger.info("Calling Gemini 2.5 Flash Lite for final recommendations...")

        # Retry once on 429 quota errors before falling back
        last_exc = None
        response = None
        for attempt in range(2):
            try:
                response = model.generate_content(user_msg)
                break
            except Exception as exc:
                last_exc = exc
                if "429" in str(exc) or "quota" in str(exc).lower() or "resource_exhausted" in str(exc).lower():
                    if attempt == 0:
                        logger.warning("Gemini 429 quota hit, waiting 65s before retry...")
                        _time.sleep(65)
                    else:
                        raise
                else:
                    raise

        raw_output = response.text.strip()

        if raw_output.startswith("```"):
            lines = raw_output.split("\n")
            raw_output = "\n".join(
                line for line in lines
                if not line.strip().startswith("```")
            ).strip()

        parsed = json.loads(raw_output)

        if isinstance(parsed, dict):
            for key in ["recommendations", "places", "results", "top_5", "top5"]:
                if key in parsed:
                    recommendations = parsed[key]
                    break
            else:
                recommendations = list(parsed.values())[0] if parsed else []
        else:
            recommendations = parsed


        name_to_place = {p["name"].lower(): p for p in candidates}
        for rec in recommendations:
            rec_name_lower = rec.get("name", "").lower()
            for place_name, place_data in name_to_place.items():
                if rec_name_lower in place_name or place_name in rec_name_lower:
                    rec["sources"] = place_data.get("sources", [])[:3]
                    rec["lat"] = place_data.get("lat")
                    rec["lon"] = place_data.get("lon")
                    rec["has_reddit"] = place_data.get("has_reddit", False)
                    if not rec.get("distance"):
                        rec["distance"] = f"{place_data.get('distance_km', 0)} km away"
                    if not rec.get("address"):
                        rec["address"] = place_data.get("address", "")
                    if not rec.get("website"):
                        rec["website"] = place_data.get("website", "")
                    break

        return {
            **state,
            "recommendations": recommendations[:TOP_N],
            "recommender_status": "success",
            "total_analyzed": len(places),
            "llm_model": "gemini-2.5-flash-lite"
        }

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Gemini JSON output: {e}")
        return build_fallback_recommendations(state, candidates, query, location_name)
    except Exception as e:
        logger.error(f"Recommender agent failed: {e}")
        return build_fallback_recommendations(state, candidates, query, location_name)


def build_fallback_recommendations(state: dict, places: list[dict], query: str, location_name: str) -> dict:
    """
    Fallback recommendation builder when LLM is unavailable.
    Creates structured recommendations from research data alone.
    """
    recommendations = []
    for i, place in enumerate(places[:TOP_N]):
        summary = place.get("research_summary", "Highly rated local spot worth visiting.")
        web_summary = place.get("web_summary", "")
        reddit_summary = place.get("reddit_summary", "")
        
        def smart_truncate(text, max_length):
            if not text or len(text) <= max_length:
                return text
            truncated = text[:max_length]
            last_period = truncated.rfind('.')
            last_exclaim = truncated.rfind('!')
            last_question = truncated.rfind('?')
            best_cut = max(last_period, last_exclaim, last_question)
            if best_cut > max_length * 0.6:  
                return text[:best_cut + 1].strip()
            last_space = truncated.rfind(' ')
            if last_space > 0:
                return truncated[:last_space].strip() + "..."
            return truncated + "..."
        
        amenity = place.get('amenity', 'place').replace('_', ' ').title()
        distance = place.get('distance_km', '?')
        
        highlights = []
        if distance != '?':
            highlights.append(f"Just {distance} km from your location")
        
        if place.get('cuisine'):
            highlights.append(f"Cuisine: {place.get('cuisine').title()}")
        else:
            highlights.append(f"Category: {amenity}")
        
        source_count = place.get('source_count', 0)
        if source_count > 0:
            highlights.append(f"Featured in {source_count} sources")
        else:
            highlights.append("Local favorite")
        
        if reddit_summary:
            truncated_reddit = smart_truncate(reddit_summary, 300)
            if len(truncated_reddit) > 20:
                reddit_text = f"Reddit users mention: {truncated_reddit}"
            else:
                reddit_text = truncated_reddit
        else:
            reddit_text = "Limited Reddit discussions found. Check Yelp and TripAdvisor for more community reviews."
            
        if web_summary:
            truncated_web = smart_truncate(web_summary, 300)
            if len(truncated_web) > 20:
                web_text = f"Reviewers say: {truncated_web}"
            else:
                web_text = truncated_web
        else:
            web_text = "No additional web reviews found."
        
        insider_tips = {
            'restaurant': "Call ahead for reservations, especially on weekends.",
            'bar': "Check happy hour specials and live music schedules.",
            'cafe': "Arrive early for the best pastry selection.",
            'pub': "Ask locals about the best beers on tap.",
            'brewery': "Try the tasting flight to sample multiple brews.",
            'museum': "Visit during weekday mornings to avoid crowds.",
            'park': "Best visited during golden hour for photos.",
        }
        amenity_key = place.get('amenity', '').lower()
        insider_tip = insider_tips.get(amenity_key, "Call ahead to confirm hours and availability.")
        
        rec = {
            "rank": i + 1,
            "name": place["name"],
            "tagline": f"A popular {amenity.lower()} in {location_name.split(',')[0]}",
            "why_visit": smart_truncate(summary, 350),
            "highlights": highlights,
            "web_says": web_text,
            "reddit_says": reddit_text,
            "best_for": f"Those looking for {query.split()[0] if query else 'great local experiences'}",
            "insider_tip": insider_tip,
            "distance": f"{distance} km away",
            "address": place.get("address", ""),
            "website": place.get("website", ""),
            "sources": place.get("sources", [])[:3],
            "lat": place.get("lat"),
            "lon": place.get("lon"),
            "has_reddit": place.get("has_reddit", False),
            "category": place.get("amenity", "place")
        }
        recommendations.append(rec)

    return {
        **state,
        "recommendations": recommendations,
        "recommender_status": "success",
        "total_analyzed": len(places),
        "llm_model": "fallback"
    }
