"""
LangGraph Pipeline: Orchestrates the 4-agent workflow.
Node 1 → Node 2 → Node 3 → Node 4
"""

import logging
from typing import TypedDict, Optional, Any
from langgraph.graph import StateGraph, END

from agents.geolocation_agent import run_geolocation_agent
from agents.discovery_agent import run_discovery_agent
from agents.research_agent import run_research_agent
from agents.recommender_agent import run_recommender_agent

logger = logging.getLogger(__name__)


class AgentState(TypedDict, total=False):

    query: str
    lat: Optional[float]
    lon: Optional[float]
    user_ip: Optional[str]
    location_name: Optional[str]

    geolocation_source: str
    geolocation_status: str

    discovered_places: list
    place_type: str
    discovery_count: int
    discovery_status: str
    search_tags: list

    researched_places: list
    research_status: str
    research_count: int

    recommendations: list
    recommender_status: str
    total_analyzed: int
    llm_model: str
    error: Optional[str]


def should_continue_after_geolocation(state: AgentState) -> str:
    """Route after geolocation node."""
    if state.get("geolocation_status") == "success":
        return "discovery"
    return "end_error"


def should_continue_after_discovery(state: AgentState) -> str:
    """Route after discovery node."""
    if state.get("discovery_status") == "success":
        return "research"
    elif state.get("discovery_status") == "no_results":
        return "end_no_results"
    return "end_error"


def should_continue_after_research(state: AgentState) -> str:
    """Route after research node."""
    return "recommender"


def error_node(state: AgentState) -> AgentState:
    """Terminal error state."""
    return {
        **state,
        "recommendations": [],
        "recommender_status": "failed"
    }


def no_results_node(state: AgentState) -> AgentState:
    """Terminal state when no places found."""
    return {
        **state,
        "recommendations": [],
        "recommender_status": "no_results",
        "error": f"No {state.get('place_type', 'places')} found near your location. Try a different search or expand the area."
    }


def build_pipeline() -> StateGraph:
    """
    Build and compile the LangGraph pipeline with 4 agent nodes.
    """
    workflow = StateGraph(AgentState)

   
    workflow.add_node("geolocation", run_geolocation_agent)
    workflow.add_node("discovery", run_discovery_agent)
    workflow.add_node("research", run_research_agent)
    workflow.add_node("recommender", run_recommender_agent)
    workflow.add_node("end_error", error_node)
    workflow.add_node("end_no_results", no_results_node)

    
    workflow.set_entry_point("geolocation")

    
    workflow.add_conditional_edges(
        "geolocation",
        should_continue_after_geolocation,
        {
            "discovery": "discovery",
            "end_error": "end_error"
        }
    )

    workflow.add_conditional_edges(
        "discovery",
        should_continue_after_discovery,
        {
            "research": "research",
            "end_no_results": "end_no_results",
            "end_error": "end_error"
        }
    )

    workflow.add_conditional_edges(
        "research",
        should_continue_after_research,
        {
            "recommender": "recommender"
        }
    )

    workflow.add_edge("recommender", END)
    workflow.add_edge("end_error", END)
    workflow.add_edge("end_no_results", END)

    return workflow.compile()


_pipeline = None


def get_pipeline():
    global _pipeline
    if _pipeline is None:
        _pipeline = build_pipeline()
    return _pipeline


def run_pipeline(
    query: str,
    lat: float = None,
    lon: float = None,
    user_ip: str = None,
    location_name: str = None
) -> dict:
    """
    Run the full 4-agent pipeline for a user query.

    Args:
        query: User's search query (e.g. "best restaurants near me")
        lat: Browser-provided latitude (optional)
        lon: Browser-provided longitude (optional)
        user_ip: Client IP address for IP-based geolocation fallback
        location_name: Pre-resolved location name (optional)

    Returns:
        Final state dict with 'recommendations' list and metadata
    """
    pipeline = get_pipeline()

    initial_state = {
        "query": query,
        "lat": lat,
        "lon": lon,
        "user_ip": user_ip,
        "location_name": location_name,
    }

    logger.info(f"Starting pipeline for query: '{query}'")
    try:
        final_state = pipeline.invoke(initial_state)
        logger.info(
            f"Pipeline complete. Status: {final_state.get('recommender_status')} | "
            f"Recommendations: {len(final_state.get('recommendations', []))}"
        )
        return final_state
    except Exception as e:
        logger.error(f"Pipeline crashed: {e}", exc_info=True)
        return {
            **initial_state,
            "recommendations": [],
            "recommender_status": "failed",
            "error": f"Pipeline error: {str(e)}"
        }
