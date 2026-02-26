import requests

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

def test_overpass_manual(tags: list[tuple[str, str]], lat: float, lon: float, radius: int = 5000):
    print(f"\n--- Testing Manual Tags {tags} near ({lat}, {lon}) ---")
    
    tag_filters = "".join([f'["{key}"="{value}"]' for key, value in tags])
    
    overpass_query = f"""
[out:json][timeout:25];
(
  node{tag_filters}(around:{radius},{lat},{lon});
  way{tag_filters}(around:{radius},{lat},{lon});
);
out center tags 30;
"""
    
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
    print("Testing for pizza:")
    test_overpass_manual([("amenity", "restaurant"), ("cuisine", "pizza")], lat, lon)

    print("\nTesting for indian food:")
    test_overpass_manual([("amenity", "restaurant"), ("cuisine", "indian")], lat, lon)
    
    print("\nTesting for mexican food:")
    test_overpass_manual([("amenity", "restaurant"), ("cuisine", "mexican")], lat, lon)
