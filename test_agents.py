"""
Test script to verify research and recommender agents are working correctly.
"""

import os
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

logger = logging.getLogger(__name__)

def test_research_agent():
    """Test the research agent with sample data."""
    print("\n" + "="*60)
    print("TESTING RESEARCH AGENT")
    print("="*60)
    
    from agents.research_agent import run_research_agent
    
    # Mock state with discovered places
    test_state = {
        "discovery_status": "success",
        "discovered_places": [
            {
                "id": "1",
                "name": "Test Restaurant",
                "lat": 37.7749,
                "lon": -122.4194,
                "distance_km": 1.5,
                "amenity": "restaurant",
                "cuisine": "italian",
                "address": "123 Test St, San Francisco, CA",
                "phone": "",
                "website": "",
                "opening_hours": ""
            }
        ],
        "location_name": "San Francisco, California",
        "query": "best italian restaurants"
    }
    
    try:
        result = run_research_agent(test_state)
        
        if result.get("research_status") == "success":
            print("[OK] Research Agent: SUCCESS")
            researched = result.get("researched_places", [])
            print(f"   - Researched {len(researched)} places")
            if researched:
                place = researched[0]
                print(f"   - Sample place: {place['name']}")
                print(f"   - Research score: {place.get('research_score', 0):.3f}")
                print(f"   - Sources found: {place.get('source_count', 0)}")
                print(f"   - Has Reddit: {place.get('has_reddit', False)}")
        else:
            print(f"[FAIL] Research Agent: FAILED - {result.get('error', 'Unknown error')}")
        
        return result
        
    except Exception as e:
        print(f"[ERROR] Research Agent: EXCEPTION - {str(e)}")
        logger.error("Research agent test failed", exc_info=True)
        return None


def test_recommender_agent(research_result=None):
    """Test the recommender agent with sample data."""
    print("\n" + "="*60)
    print("TESTING RECOMMENDER AGENT")
    print("="*60)
    
    from agents.recommender_agent import run_recommender_agent
    
    # Use research result if provided, otherwise create mock data
    if research_result and research_result.get("research_status") == "success":
        test_state = research_result
    else:
        test_state = {
            "research_status": "success",
            "researched_places": [
                {
                    "id": "1",
                    "name": "Test Restaurant",
                    "lat": 37.7749,
                    "lon": -122.4194,
                    "distance_km": 1.5,
                    "amenity": "restaurant",
                    "cuisine": "italian",
                    "address": "123 Test St, San Francisco, CA",
                    "phone": "",
                    "website": "",
                    "opening_hours": "",
                    "research_results": [],
                    "research_summary": "Highly rated Italian restaurant with great pasta.",
                    "reddit_summary": "Reddit users love their carbonara.",
                    "sources": ["https://yelp.com/test", "https://reddit.com/test"],
                    "source_count": 2,
                    "has_reddit": True,
                    "has_blog": False,
                    "research_score": 0.85
                }
            ],
            "location_name": "San Francisco, California",
            "query": "best italian restaurants"
        }
    
    try:
        result = run_recommender_agent(test_state)
        
        if result.get("recommender_status") == "success":
            print("[OK] Recommender Agent: SUCCESS")
            recommendations = result.get("recommendations", [])
            print(f"   - Generated {len(recommendations)} recommendations")
            print(f"   - LLM model: {result.get('llm_model', 'unknown')}")
            
            if recommendations:
                rec = recommendations[0]
                print(f"\n   Top Recommendation:")
                print(f"   - Name: {rec.get('name', 'N/A')}")
                print(f"   - Rank: {rec.get('rank', 'N/A')}")
                print(f"   - Tagline: {rec.get('tagline', 'N/A')[:60]}...")
                print(f"   - Price vibe: {rec.get('price_vibe', 'N/A')}")
        else:
            print(f"[FAIL] Recommender Agent: FAILED - {result.get('error', 'Unknown error')}")
        
        return result
        
    except Exception as e:
        print(f"[ERROR] Recommender Agent: EXCEPTION - {str(e)}")
        logger.error("Recommender agent test failed", exc_info=True)
        return None


def test_api_keys():
    """Verify API keys are configured."""
    print("\n" + "="*60)
    print("CHECKING API CONFIGURATION")
    print("="*60)
    
    tavily_key = os.getenv("TAVILY_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")
    
    if tavily_key:
        print(f"[OK] TAVILY_API_KEY: Configured ({tavily_key[:10]}...)")
    else:
        print("[FAIL] TAVILY_API_KEY: NOT CONFIGURED")
    
    if gemini_key:
        print(f"[OK] GEMINI_API_KEY: Configured ({gemini_key[:10]}...)")
    else:
        print("[FAIL] GEMINI_API_KEY: NOT CONFIGURED")
    
    return bool(tavily_key and gemini_key)


if __name__ == "__main__":
    print("\n*** LOCAL GUIDE - AGENT TESTING SUITE ***")
    print("=" * 60)
    
    # Check API keys first
    if not test_api_keys():
        print("\n[WARNING] Missing API keys. Some tests may fail.")
    
    # Test research agent
    research_result = test_research_agent()
    
    # Test recommender agent (with research results if available)
    recommender_result = test_recommender_agent(research_result)
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    if research_result and research_result.get("research_status") == "success":
        print("[OK] Research Agent: Working")
    else:
        print("[FAIL] Research Agent: Not working")
    
    if recommender_result and recommender_result.get("recommender_status") == "success":
        print("[OK] Recommender Agent: Working")
    else:
        print("[FAIL] Recommender Agent: Not working")
    
    print("\n" + "="*60)
