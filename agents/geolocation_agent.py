import os
import re
import json
import requests
import logging
import google.generativeai as genai

logger = logging.getLogger(__name__)


def extract_location_from_query(query: str) -> str | None:
   
    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key:
        location = _extract_location_with_gemini(query, gemini_key)
        if location:
            logger.info(f"Gemini extracted location from query: '{location}'")
            return location

    location = _extract_location_with_regex(query)
    if location:
        logger.info(f"Regex extracted location from query: '{location}'")
        return location

    return None


def _extract_location_with_gemini(query: str, api_key: str) -> str | None:

    try:
        genai.configure(api_key=api_key)
        
        system_prompt = (
            "You are a geographic location extractor. "
            "Given a user's search query, extract ONLY the specific geographic location "
            "they are asking about (city, neighbourhood, landmark, region, etc.). "
            "If the query says 'near me', 'nearby', or has NO specific place name, respond with exactly: NONE. "
            "If a location is found, respond with ONLY the clean location name no extra words, "
            "no punctuation, no explanation. Examples:\n"
            "  'best tacos in Austin TX' Austin, TX\n"
            "  'coffee shops near Chicago Loop' Chicago Loop, Chicago\n"
            "  'sushi in Mission District San Francisco' Mission District, San Francisco\n"
            "  'rooftop bars near me' NONE\n"
            "  'best restaurants nearby' NONE\n"
            "  'hidden gems in Brooklyn' Brooklyn, New York\n"
            "  'top rated ramen' NONE"
        )

        model = genai.GenerativeModel(
            model_name="models/gemini-2.5-flash",
            generation_config={"temperature": 0.0, "max_output_tokens": 50},
            system_instruction=system_prompt
        )

        response = model.generate_content(query)
        result = response.text.strip().strip('"').strip("'")

        if result.upper() == "NONE" or not result:
            return None

        if len(result) > 100 or len(result.split()) > 8:
            logger.warning(f"Gemini location result seems too long, ignoring: '{result}'")
            return None

        return result

    except Exception as e:
        logger.warning(f"Gemini location extraction failed: {e}")
        return None


def _extract_location_with_regex(query: str) -> str | None:
        
    near_me_patterns = [
        r'\bnear\s+me\b', r'\bnearby\b', r'\bclose\s+to\s+me\b',
        r'\baround\s+me\b', r'\bmy\s+area\b', r'\bmy\s+location\b',
    ]
    query_lower = query.lower()
    for pattern in near_me_patterns:
        if re.search(pattern, query_lower):
            return None  

    location_triggers = [
        r'\b(?:in|near|around|at|close to)\s+([A-Z][a-zA-Z\s,]{2,40}?)(?:\s*$|[?.!,])',
        r'\b(?:in|near|around|at)\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){0,3})',
    ]

    for pattern in location_triggers:
        match = re.search(pattern, query)
        if match:
            candidate = match.group(1).strip().strip(".,?!")
            exclude = {"me", "my", "the", "a", "an", "best", "top", "good", "great", "this", "that"}
            words = candidate.split()
            place_words = []
            for w in words:
                clean = w.strip(",.?!")
                if clean.lower() in exclude:
                    break
                place_words.append(clean)
            if place_words and len(place_words) <= 5:
                return " ".join(place_words)

    return None



def geocode_place_name(place_name: str) -> dict | None:

    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {"q": place_name, "format": "json", "limit": 1}
        headers = {"User-Agent": "LocalGuide-App/1.0"}
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data:
           
            raw_display = data[0].get("display_name", place_name)
            parts = [p.strip() for p in raw_display.split(",")]
            display = ", ".join(parts[:2]) if len(parts) >= 2 else raw_display
            return {
                "lat": float(data[0]["lat"]),
                "lon": float(data[0]["lon"]),
                "display_name": display,
                "source": "nominatim"
            }
    except Exception as e:
        logger.error(f"Nominatim geocoding failed for '{place_name}': {e}")
    return None



def get_location_from_ip(ip_address: str | None = None) -> dict | None:

    try:
        target = ip_address if ip_address else ""
        url = f"http://ip-api.com/json/{target}"
        params = {"fields": "status,message,lat,lon,city,regionName,country,query"}
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") == "success":
            city = data.get("city", "")
            region = data.get("regionName", "")
            country = data.get("country", "")
            display = ", ".join(filter(None, [city, region, country]))
            return {
                "lat": data["lat"],
                "lon": data["lon"],
                "display_name": display or "Your Location",
                "city": city,
                "source": "ip-api"
            }
        else:
            logger.warning(f"ip-api returned non-success: {data.get('message')}")
    except Exception as e:
        logger.error(f"IP geolocation failed: {e}")
    return None



def run_geolocation_agent(state: dict) -> dict:
    
    query = state.get("query", "")
    lat = state.get("lat")
    lon = state.get("lon")

    query_location = extract_location_from_query(query)

    if lat is not None and lon is not None:
        if query_location:
            logger.info(
                f"Browser GPS available but query mentions '{query_location}' — "
                f"geocoding query location instead."
            )
            coords = geocode_place_name(query_location)
            if coords:
                return {
                    **state,
                    "lat": coords["lat"],
                    "lon": coords["lon"],
                    "location_name": coords["display_name"],
                    "geolocation_source": "query_text",
                    "geolocation_status": "success"
                }
            logger.warning(f"Could not geocode '{query_location}', falling back to browser GPS")

        logger.info(f"Using browser GPS coordinates: {lat:.4f}, {lon:.4f}")
        display_name = state.get("location_name") or f"{lat:.4f}, {lon:.4f}"
        return {
            **state,
            "lat": float(lat),
            "lon": float(lon),
            "location_name": display_name,
            "geolocation_source": "browser",
            "geolocation_status": "success"
        }

    if query_location:
        logger.info(f"No GPS — geocoding query-extracted location: '{query_location}'")
        coords = geocode_place_name(query_location)
        if coords:
            return {
                **state,
                "lat": coords["lat"],
                "lon": coords["lon"],
                "location_name": coords["display_name"],
                "geolocation_source": "query_text",
                "geolocation_status": "success"
            }
        logger.warning(f"Could not geocode '{query_location}', falling back to IP")

    user_ip = state.get("user_ip")
    logger.info(f"Using IP-based geolocation (IP: {user_ip or 'auto'})")
    coords = get_location_from_ip(user_ip)
    if coords:
        return {
            **state,
            "lat": coords["lat"],
            "lon": coords["lon"],
            "location_name": coords["display_name"],
            "geolocation_source": "ip-api",
            "geolocation_status": "success"
        }

    return {
        **state,
        "geolocation_status": "failed",
        "error": (
            "Could not determine your location. "
            "Please enable location access or mention a city in your search "
            "(e.g. 'best coffee in Austin')."
        )
    }
