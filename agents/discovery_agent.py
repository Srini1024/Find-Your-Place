import os
import re
import json
import math
import requests
import logging
import google.generativeai as genai
from typing import Optional

logger = logging.getLogger(__name__)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

DEFAULT_RADIUS = 5000  
MAX_RADIUS = 15000     
OSM_TAG_REFERENCE = """
Common OpenStreetMap (OSM) tag key=value pairs you can use:

FOOD & DRINK:
  amenity=restaurant        — general restaurants
  amenity=cafe              — cafes, coffee shops, brunch spots
  amenity=bar               — bars, cocktail lounges, pubs
  amenity=pub               — traditional pubs
  amenity=fast_food         — fast food joints
  amenity=food_court        — food courts
  amenity=ice_cream         — ice cream parlours
  amenity=bakery            — bakeries
  amenity=nightclub         — nightclubs
  amenity=brewery           — breweries
  shop=wine                 — wine bars/shops
  cuisine=sushi             — sushi (used with amenity=restaurant)
  cuisine=pizza             — pizza places
  cuisine=burger            — burger joints
  cuisine=ramen             — ramen restaurants
  cuisine=mexican           — Mexican food
  cuisine=indian            — Indian food
  cuisine=thai              — Thai food
  cuisine=chinese           — Chinese food
  cuisine=italian           — Italian food
  cuisine=korean            — Korean food
  cuisine=vegan             — vegan restaurants
  cuisine=vegetarian        — vegetarian restaurants
  cuisine=seafood           — seafood restaurants
  cuisine=steak_house       — steakhouses
  cuisine=breakfast;brunch  — brunch spots

TOURISM & ATTRACTIONS:
  tourism=museum            — museums
  tourism=hotel             — hotels
  tourism=attraction        — general attractions / landmarks
  tourism=gallery           — art galleries
  tourism=viewpoint         — scenic viewpoints
  tourism=zoo               — zoos
  tourism=theme_park        — theme parks

LEISURE & WELLNESS:
  leisure=park              — parks, green spaces
  leisure=fitness_centre    — gyms, fitness centres
  leisure=sports_centre     — sports centres
  leisure=spa               — spas
  leisure=swimming_pool     — swimming pools
  leisure=miniature_golf    — mini golf

SHOPPING:
  shop=mall                 — shopping malls
  shop=department_store     — department stores
  shop=supermarket          — supermarkets
  shop=books                — bookshops
  shop=clothes              — clothing stores

CULTURE & ENTERTAINMENT:
  amenity=cinema            — movie theatres
  amenity=theatre           — theatres / performing arts
  amenity=arts_centre       — arts centres
  amenity=library           — libraries
  amenity=community_centre  — community centres
"""


def resolve_osm_tags_with_gemini(query: str, api_key: str) -> list[tuple[str, str]] | None:
    try:
        genai.configure(api_key=api_key)
        
        system_prompt = (
            "You are an OpenStreetMap (OSM) tag expert. "
            "Given a user's place search query, return the most relevant OSM tags to search for. "
            "Use ONLY valid OSM tags from the reference provided. "
            "Respond with ONLY a valid JSON array of [key, value] pairs. No explanation, no markdown. "
            "Limit to 3 tags maximum prefer quality over quantity. "
            "Examples:\n"
            '  "best sushi near me" [["amenity","restaurant"],["cuisine","sushi"]]\n'
            '  "craft cocktail bars" [["amenity","bar"]]\n'
            '  "vegan restaurants" [["amenity","restaurant"],["cuisine","vegan"]]\n'
            '  "cozy coffee shops" [["amenity","cafe"]]\n'
            '  "late night ramen" [["amenity","restaurant"],["cuisine","ramen"]]\n'
            '  "art museums" [["tourism","museum"]]\n'
            '  "scenic parks" [["leisure","park"]]\n'
            f"\n\nOSM Tag Reference:\n{OSM_TAG_REFERENCE}"
        )

        model = genai.GenerativeModel(
            model_name="models/gemini-2.5-flash",
            generation_config={"temperature": 0.0, "max_output_tokens": 150},
            system_instruction=system_prompt
        )

        response = model.generate_content(f'Query: "{query}"')
        raw = response.text.strip()

        if raw.startswith("```"):
            raw = "\n".join(
                line for line in raw.split("\n")
                if not line.strip().startswith("```")
            ).strip()

        parsed = json.loads(raw)

        if not isinstance(parsed, list) or not parsed:
            return None

        tags = []
        for item in parsed:
            if isinstance(item, list) and len(item) == 2:
                key, value = str(item[0]), str(item[1])
               
                if re.match(r'^[a-z_:]+$', key) and re.match(r'^[a-z_: ;]+$', value):
                    tags.append((key, value))

        if tags:
            logger.info(f"Gemini resolved '{query}' → OSM tags: {tags}")
            return tags

    except json.JSONDecodeError as e:
        logger.warning(f"Gemini tag resolver returned invalid JSON: {e}")
    except Exception as e:
        logger.warning(f"Gemini tag resolution failed: {e}")

    return None

_FALLBACK_TAG_RULES: list[tuple[list[str], list[tuple[str, str]]]] = [
    (["sushi", "japanese"],             [("amenity", "restaurant"), ("cuisine", "sushi")]),
    (["ramen", "noodle"],               [("amenity", "restaurant"), ("cuisine", "ramen")]),
    (["pizza"],                         [("amenity", "restaurant"), ("cuisine", "pizza")]),
    (["burger", "burgers"],             [("amenity", "fast_food"), ("amenity", "restaurant")]),
    (["taco", "tacos", "mexican"],      [("amenity", "restaurant"), ("cuisine", "mexican")]),
    (["indian", "curry"],               [("amenity", "restaurant"), ("cuisine", "indian")]),
    (["chinese", "dim sum"],            [("amenity", "restaurant"), ("cuisine", "chinese")]),
    (["thai"],                          [("amenity", "restaurant"), ("cuisine", "thai")]),
    (["italian", "pasta"],              [("amenity", "restaurant"), ("cuisine", "italian")]),
    (["korean", "bbq"],                 [("amenity", "restaurant"), ("cuisine", "korean")]),
    (["vegan"],                         [("amenity", "restaurant"), ("cuisine", "vegan")]),
    (["vegetarian"],                    [("amenity", "restaurant"), ("cuisine", "vegetarian")]),
    (["seafood", "fish"],               [("amenity", "restaurant"), ("cuisine", "seafood")]),
    (["steak", "steakhouse"],           [("amenity", "restaurant"), ("cuisine", "steak_house")]),
    (["brunch", "breakfast"],           [("amenity", "cafe"), ("amenity", "restaurant")]),
    (["cocktail", "cocktails"],         [("amenity", "bar")]),
    (["craft beer", "brewery", "brew"], [("amenity", "bar"), ("amenity", "brewery")]),
    (["wine"],                          [("amenity", "bar"), ("shop", "wine")]),
    (["nightclub", "club", "nightlife"],[("amenity", "nightclub"), ("amenity", "bar")]),
    (["pub", "pubs"],                   [("amenity", "pub")]),
    (["bar", "bars"],                   [("amenity", "bar")]),
    (["coffee", "cafe", "cafes", "espresso", "latte"], [("amenity", "cafe")]),
    (["bakery", "pastry"],              [("amenity", "cafe"), ("shop", "bakery")]),
    (["restaurant", "restaurants", "eat", "dining", "dinner", "lunch"],
                                        [("amenity", "restaurant")]),
    (["food", "foodie", "eats"],        [("amenity", "restaurant"), ("amenity", "cafe")]),
    (["fast food", "takeout", "takeaway"], [("amenity", "fast_food")]),
    (["museum", "museums"],             [("tourism", "museum")]),
    (["gallery", "art"],                [("tourism", "gallery"), ("tourism", "museum")]),
    (["hotel", "hotels", "stay", "accommodation"], [("tourism", "hotel")]),
    (["landmark", "sightseeing", "attraction"], [("tourism", "attraction")]),
    (["zoo"],                           [("tourism", "zoo")]),
    (["theme park", "amusement"],       [("tourism", "theme_park")]),
    (["park", "parks", "nature", "green space"], [("leisure", "park")]),
    (["gym", "fitness", "workout"],     [("leisure", "fitness_centre")]),
    (["spa", "wellness", "massage"],    [("leisure", "spa")]),
    (["pool", "swimming"],              [("leisure", "swimming_pool")]),
    (["cinema", "movie", "film"],       [("amenity", "cinema")]),
    (["theatre", "theater", "show", "play"], [("amenity", "theatre")]),
    (["mall", "shopping center"],       [("shop", "mall")]),
    (["bookshop", "bookstore"],         [("shop", "books")]),
]


def resolve_osm_tags_with_fallback(query: str) -> list[tuple[str, str]]:

    query_lower = query.lower()
    for keywords, tags in _FALLBACK_TAG_RULES:
        if any(kw in query_lower for kw in keywords):
            logger.info(f"Fallback tag resolver matched '{query}' → {tags}")
            return tags

    logger.info("No specific match, using generic attraction/restaurant tags")
    return [("amenity", "restaurant"), ("tourism", "attraction"), ("amenity", "bar")]


def detect_place_tags(query: str) -> list[tuple[str, str]]:
    """
    Resolve a natural language query to OSM search tags.
    Uses Gemini for intelligent understanding; regex as a zero-cost fallback.
    """
    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key:
        tags = resolve_osm_tags_with_gemini(query, gemini_key)
        if tags:
            return tags
        logger.warning("Gemini tag resolution failed, using regex fallback")

    return resolve_osm_tags_with_fallback(query)



def build_overpass_query(lat: float, lon: float, tags: list[tuple[str, str]], radius: int) -> str:
    tag_queries = []
    for key, value in tags:
        tag_queries.append(
            f'  node["{key}"="{value}"](around:{radius},{lat},{lon});\n'
            f'  way["{key}"="{value}"](around:{radius},{lat},{lon});'
        )
    union_body = "\n  ".join(tag_queries)
    return f"""
[out:json][timeout:25];
(
  {union_body}
);
out center tags 30;
"""


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def build_address(tags: dict) -> str:
    parts = []
    if tags.get("addr:housenumber"):
        parts.append(tags["addr:housenumber"])
    if tags.get("addr:street"):
        parts.append(tags["addr:street"])
    if tags.get("addr:city"):
        parts.append(tags["addr:city"])
    if tags.get("addr:postcode"):
        parts.append(tags["addr:postcode"])
    return ", ".join(parts) if parts else ""


def parse_overpass_results(elements: list, user_lat: float, user_lon: float) -> list[dict]:
    places = []
    for el in elements:
        tags = el.get("tags", {})
        name = tags.get("name") or tags.get("name:en")
        if not name:
            continue

        if el.get("type") == "node":
            place_lat, place_lon = el.get("lat"), el.get("lon")
        else:
            center = el.get("center", {})
            place_lat, place_lon = center.get("lat"), center.get("lon")

        if place_lat is None or place_lon is None:
            continue

        distance = haversine_distance(user_lat, user_lon, place_lat, place_lon)

        places.append({
            "id": str(el.get("id", "")),
            "name": name,
            "lat": place_lat,
            "lon": place_lon,
            "distance_m": round(distance),
            "distance_km": round(distance / 1000, 2),
            "amenity": tags.get("amenity") or tags.get("tourism") or tags.get("leisure") or "place",
            "cuisine": tags.get("cuisine", ""),
            "address": build_address(tags),
            "phone": tags.get("phone", tags.get("contact:phone", "")),
            "website": tags.get("website", tags.get("contact:website", "")),
            "opening_hours": tags.get("opening_hours", ""),
            "rating": tags.get("stars", ""),
            "wheelchair": tags.get("wheelchair", ""),
            "osm_type": el.get("type"),
        })

    places.sort(key=lambda x: x["distance_m"])
    seen_names: set[str] = set()
    unique = []
    for p in places:
        key = p["name"].lower().strip()
        if key not in seen_names:
            seen_names.add(key)
            unique.append(p)
    return unique


def query_overpass(lat: float, lon: float, tags: list[tuple[str, str]]) -> list[dict]:

    for radius in [DEFAULT_RADIUS, MAX_RADIUS]:
        query = build_overpass_query(lat, lon, tags, radius)
        try:
            resp = requests.post(
                OVERPASS_URL,
                data=query.encode("utf-8"),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30
            )
            resp.raise_for_status()
            places = parse_overpass_results(resp.json().get("elements", []), lat, lon)
            if places:
                logger.info(f"Found {len(places)} places within {radius}m")
                return places
            logger.warning(f"No places found within {radius}m, trying larger radius")
        except Exception as e:
            logger.error(f"Overpass API error: {e}")
            break
    return []


def run_discovery_agent(state: dict) -> dict:
    """
    Discovers nearby places matching the user's query using Overpass API.

    Flow:
      1. Use Gemini (or regex fallback) to map the natural language query → OSM tags
      2. Query Overpass API with those tags around the resolved lat/lon
      3. If empty results, try a broad fallback search
      4. Return top 15 places sorted by distance

    Expected state keys:
      - lat, lon: resolved coordinates from geolocation agent
      - query: user's original natural language search query
      - geolocation_status: must be "success"

    Returns updated state with:
      - discovered_places: up to 15 nearby place dicts
      - place_type: primary OSM amenity type detected
      - discovery_count: number of results
      - discovery_status: "success" | "no_results" | "failed"
      - search_tags: the OSM tags used for the search
    """
    if state.get("geolocation_status") != "success":
        return {
            **state,
            "discovery_status": "failed",
            "error": state.get("error", "Geolocation failed, cannot discover places")
        }

    lat = state["lat"]
    lon = state["lon"]
    query = state.get("query", "")
    tags = detect_place_tags(query)
    place_type_label = tags[0][1] if tags else "place"

    logger.info(f"Discovering '{query}' → tags={tags} near ({lat:.4f}, {lon:.4f})")
    places = query_overpass(lat, lon, tags)

    if not places:
        logger.warning("No results with specific tags, trying broad fallback search")
        broad_tags = [("amenity", "restaurant"), ("amenity", "bar"), ("tourism", "attraction")]
        places = query_overpass(lat, lon, broad_tags)

    top_places = places[:5]

    return {
        **state,
        "discovered_places": top_places,
        "place_type": place_type_label,
        "discovery_count": len(top_places),
        "discovery_status": "success" if top_places else "no_results",
        "search_tags": tags,
    }
