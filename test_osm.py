import os
import requests
import google.generativeai as genai

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

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
"""

def resolve_osm_tags_with_gemini(query: str, api_key: str) -> list:
    import json
    import re
    genai.configure(api_key=api_key)
    
    system_prompt = (
        "You are an OpenStreetMap (OSM) tag expert. "
        "Given a user's place search query, return the most relevant OSM tags to search for. "
        "Use ONLY valid OSM tags from the reference provided. "
        "Respond with ONLY a valid JSON array of [key, value] pairs. No explanation, no markdown. "
        "Limit to 3 tags maximum prefer quality over quantity. "
        f"\n\nOSM Tag Reference:\n{OSM_TAG_REFERENCE}"
    )

    model = genai.GenerativeModel(
        model_name="models/gemini-2.5-flash-lite",
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

    print(f"Gemini Raw Response for '{query}':\n{raw}")
    try:
        parsed = json.loads(raw)
        return parsed
    except json.JSONDecodeError as e:
        print(f"JSON Error: {e}")
        return []

def test_overpass(query: str, lat: float, lon: float, radius: int = 5000):
    from dotenv import load_dotenv
    load_dotenv()
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Set GEMINI_API_KEY in .env")
        return

    print(f"\n--- Testing '{query}' near ({lat}, {lon}) ---")
    
    tags = resolve_osm_tags_with_gemini(query, api_key)
    if not tags:
        print("Failed to resolve tags")
        return

    print(f"Resolved tags: {tags}")

    # Combine all tag filters into one string for AND logic
    tag_filters = "".join([f'["{key}"="{value}"]' for key, value in tags])
    
    overpass_query = f"""
[out:json][timeout:25];
(
  node{tag_filters}(around:{radius},{lat},{lon});
  way{tag_filters}(around:{radius},{lat},{lon});
);
out center tags 30;
"""
    
    # print(f"Overpass Query:\n{overpass_query}")
    print("\nQuerying Overpass API...")
    resp = requests.post(
        OVERPASS_URL,
        data=overpass_query.encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30
    )
    
    try:
        resp.raise_for_status()
        elements = resp.json().get("elements", [])
        print(f"\nFound {len(elements)} results:")
        for el in elements[:10]:
            name = el.get("tags", {}).get("name", "Unknown")
            cuisine = el.get("tags", {}).get("cuisine", "Unknown")
            print(f" - {name} (Cuisine: {cuisine})")
    except Exception as e:
        print(f"Error querying Overpass: {e}")

if __name__ == "__main__":

    lat, lon = "your test latitude", "your test longitude"
    test_overpass("best pizza", lat, lon)
