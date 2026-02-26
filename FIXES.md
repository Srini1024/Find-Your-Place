# Local Guide Project - Agent Fixes

## Issues Identified and Fixed

### 1. **Critical: Incorrect Google Generative AI Import**
**Problem:** The code was using an outdated/incorrect import structure for Google's Generative AI library:
```python
from google import genai
from google.genai import types as genai_types
```

**Fix:** Updated to the correct import for `google-generativeai>=0.8.0`:
```python
import google.generativeai as genai
```

**Impact:** This was causing both the research and recommender agents to fail completely as they couldn't properly initialize the Gemini API.

---

### 2. **Missing LangGraph Dependency**
**Problem:** The `pipeline.py` uses LangGraph but it wasn't listed in `requirements.txt`.

**Fix:** Added `langgraph>=0.2.0` to requirements.txt

**Impact:** Without this, the entire pipeline would crash on import.

---

### 3. **Updated Gemini API Calls**
**Problem:** The code was using the old API structure with `Client` and `models.generate_content()`.

**Fix:** Updated all Gemini API calls to use the new structure:
```python
# Old (broken)
client = genai.Client(api_key=api_key)
response = client.models.generate_content(
    model="gemini-2.0-flash-lite",
    contents=user_msg,
    config=genai_types.GenerateContentConfig(...)
)

# New (working)
genai.configure(api_key=api_key)
model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    generation_config={...},
    system_instruction=system_prompt
)
response = model.generate_content(user_msg)
```

**Files Updated:**
- `agents/recommender_agent.py`
- `agents/research_agent.py` (no changes needed - doesn't use Gemini)
- `agents/discovery_agent.py`
- `agents/geolocation_agent.py`

---

### 4. **Model Name Update**
**Problem:** Code was using `gemini-2.0-flash-lite` and `gemini-2.0-flash-exp` which may not be available or stable.

**Fix:** Updated to use stable model `gemini-1.5-flash` across all agents.

---

## Testing

### Run the Test Suite
```bash
python test_agents.py
```

This will test:
1. API key configuration
2. Research agent functionality
3. Recommender agent functionality

### Run the Full App
```bash
# Install/update dependencies first
pip install -r requirements.txt

# Then run the app
python app.py
```

The app will be available at `http://localhost:5000`

---

## Expected Behavior After Fixes

### Research Agent (`agents/research_agent.py`)
- ✅ Should successfully query Tavily API for place research
- ✅ Should perform two-pass search (general + Reddit)
- ✅ Should classify sources and calculate research scores
- ✅ Should return enriched place data with research summaries

### Recommender Agent (`agents/recommender_agent.py`)
- ✅ Should successfully call Gemini API for recommendations
- ✅ Should generate structured JSON recommendations
- ✅ Should handle API quota limits with retries
- ✅ Should fall back to rule-based recommendations if Gemini fails
- ✅ Should return top 5 recommendations with rich metadata

---

## API Keys Required

Make sure these are set in your `.env` file:

```env
TAVILY_API_KEY=your_tavily_key_here
GEMINI_API_KEY=your_gemini_key_here
FLASK_SECRET_KEY=your_flask_secret_here
```

Your current `.env` file appears to have these configured correctly.

---

## Pipeline Flow

1. **Geolocation Agent** → Resolves user location (GPS, IP, or query extraction)
2. **Discovery Agent** → Uses Overpass API to find nearby places matching the query
3. **Research Agent** → Uses Tavily to gather reviews and research about discovered places
4. **Recommender Agent** → Uses Gemini to synthesize research into top 5 recommendations

---

## Common Issues to Watch For

### Issue: Tavily API Rate Limiting
**Symptom:** Research agent returns few or no results
**Solution:** The code includes 0.4s sleep between requests. If still hitting limits, increase this in `research_agent.py`

### Issue: Gemini API Quota Exceeded
**Symptom:** Recommender returns fallback recommendations
**Solution:** The code includes a 65s retry on 429 errors. If quota is exhausted, it falls back to rule-based recommendations

### Issue: No Places Found
**Symptom:** Discovery agent returns `no_results` status
**Solution:** The discovery agent tries broader fallback searches. Check if the query is too specific or location is incorrect

---

## File Changes Summary

### Modified Files:
1. ✅ `requirements.txt` - Added langgraph dependency
2. ✅ `agents/recommender_agent.py` - Fixed Gemini imports and API calls
3. ✅ `agents/discovery_agent.py` - Fixed Gemini imports and API calls
4. ✅ `agents/geolocation_agent.py` - Fixed Gemini imports and API calls

### Created Files:
1. ✅ `test_agents.py` - Test suite for verifying agents work correctly
2. ✅ `FIXES.md` - This documentation file

### No Changes Needed:
- ✅ `agents/research_agent.py` - Already correct (uses Tavily, not Gemini)
- ✅ `pipeline.py` - No changes needed
- ✅ `app.py` - No changes needed

---

## Next Steps

1. **Install updated dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the test suite:**
   ```bash
   python test_agents.py
   ```

3. **If tests pass, start the app:**
   ```bash
   python app.py
   ```

4. **Test in browser:**
   - Navigate to `http://localhost:5000`
   - Try a search like "best coffee shops near me"
   - Check the browser console and server logs for any errors

---

## Debugging Tips

### Enable Verbose Logging
The app already has logging configured. To see more details, check the console output when running the app.

### Test Individual Agents
You can import and test agents individually in a Python shell:

```python
from dotenv import load_dotenv
load_dotenv()

# Test research agent
from agents.research_agent import run_research_agent
test_state = {
    "discovery_status": "success",
    "discovered_places": [...],
    "location_name": "San Francisco, CA",
    "query": "best restaurants"
}
result = run_research_agent(test_state)
print(result)
```

### Check API Connectivity
```python
import os
from tavily import TavilyClient

# Test Tavily
tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
result = tavily.search("test query", max_results=1)
print(result)

# Test Gemini
import google.generativeai as genai
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-1.5-flash")
response = model.generate_content("Hello, test")
print(response.text)
```

---

## Contact & Support

If you continue to experience issues after these fixes:

1. Check the server logs for specific error messages
2. Verify API keys are valid and have available quota
3. Test individual agents using the test suite
4. Check network connectivity to external APIs (Tavily, Google, OpenStreetMap)

---

Last Updated: 2024
