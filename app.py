import os
import logging
from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

from pipeline import run_pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "find-your-place-dev-key")
CORS(app)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/search", methods=["POST"])
def search():
    """
    Main search endpoint.
    Accepts JSON with:
      - query (str, required): user's search query
      - lat (float, optional): browser geolocation latitude
      - lon (float, optional): browser geolocation longitude
      - location_name (str, optional): human-readable location from browser
    Returns:
      - recommendations: top 5 place recommendations
      - metadata: pipeline execution info
    """
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    query = data.get("query", "").strip()

    if not query:
        return jsonify({"error": "Search query is required"}), 400

    user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    if user_ip and "," in user_ip:
        user_ip = user_ip.split(",")[0].strip()

    private_prefixes = ("127.", "192.168.", "10.", "172.16.", "::1", "localhost")
    if any(user_ip.startswith(p) for p in private_prefixes):
        user_ip = None 

    lat = data.get("lat")
    lon = data.get("lon")
    location_name = data.get("location_name")

    logger.info(
        f"Search request | query='{query}' | "
        f"coords=({lat}, {lon}) | ip={user_ip}"
    )

    result = run_pipeline(
        query=query,
        lat=float(lat) if lat is not None else None,
        lon=float(lon) if lon is not None else None,
        user_ip=user_ip,
        location_name=location_name
    )


    recommendations = result.get("recommendations", [])
    status = result.get("recommender_status", "unknown")

    if status == "failed":
        error_msg = result.get("error", "Something went wrong. Please try again.")
        return jsonify({
            "success": False,
            "error": error_msg,
            "recommendations": []
        }), 500

    if status == "no_results":
        return jsonify({
            "success": False,
            "error": result.get("error", "No places found near your location."),
            "recommendations": []
        }), 404

    return jsonify({
        "success": True,
        "recommendations": recommendations,
        "metadata": {
            "query": query,
            "location": result.get("location_name", ""),
            "location_source": result.get("geolocation_source", ""),
            "place_type": result.get("place_type", ""),
            "total_discovered": result.get("discovery_count", 0),
            "total_analyzed": result.get("total_analyzed", 0),
            "llm_model": result.get("llm_model", ""),
        }
    })


@app.route("/api/health", methods=["GET"])
def health():
    """Health check endpoint."""
    tavily_configured = bool(os.getenv("TAVILY_API_KEY"))
    gemini_configured = bool(os.getenv("GEMINI_API_KEY"))
    return jsonify({
        "status": "ok",
        "tavily_configured": tavily_configured,
        "gemini_configured": gemini_configured,
        "agents": ["geolocation", "discovery", "research", "recommender"]
    })


@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Not found"}), 404


@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "Internal server error"}), 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_ENV", "development") == "development"
    logger.info(f"Starting Find Your Place server on port {port}")
    app.run(debug=debug, host="0.0.0.0", port=port)
