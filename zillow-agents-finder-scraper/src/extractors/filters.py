thonfrom dataclasses import dataclass
from typing import Any, Dict, List, Optional

@dataclass
class AgentFilter:
    """
    Represents filter criteria for agent results.
    """

    location: Optional[str] = None
    zip: Optional[str] = None
    min_reviews: Optional[int] = None
    min_rating: Optional[float] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentFilter":
        return cls(
            location=data.get("location"),
            zip=data.get("zip"),
            min_reviews=data.get("min_reviews") or data.get("minReviews"),
            min_rating=data.get("min_rating") or data.get("minRating"),
        )

def _matches_location(agent: Dict[str, Any], location: Optional[str]) -> bool:
    if not location:
        return True
    agent_loc = (agent.get("location") or "").lower()
    return location.lower() in agent_loc

def _matches_zip(agent: Dict[str, Any], zip_code: Optional[str]) -> bool:
    if not zip_code:
        return True
    agent_loc = (agent.get("location") or "")
    return zip_code in agent_loc

def _matches_min_reviews(agent: Dict[str, Any], min_reviews: Optional[int]) -> bool:
    if min_reviews is None:
        return True
    reviews = agent.get("reviews")
    try:
        reviews_int = int(reviews) if reviews is not None else 0
    except (TypeError, ValueError):
        reviews_int = 0
    return reviews_int >= int(min_reviews)

def _matches_min_rating(agent: Dict[str, Any], min_rating: Optional[float]) -> bool:
    if min_rating is None:
        return True
    rating = agent.get("rating")
    try:
        rating_float = float(rating) if rating is not None else 0.0
    except (TypeError, ValueError):
        rating_float = 0.0
    return rating_float >= float(min_rating)

def matches_filter(agent: Dict[str, Any], filters: AgentFilter) -> bool:
    """
    Return True if the agent satisfies the filter criteria.
    """
    if not _matches_location(agent, filters.location):
        return False
    if not _matches_zip(agent, filters.zip):
        return False
    if not _matches_min_reviews(agent, filters.min_reviews):
        return False
    if not _matches_min_rating(agent, filters.min_rating):
        return False
    return True

def filter_agents(agents: List[Dict[str, Any]], filters: AgentFilter) -> List[Dict[str, Any]]:
    """
    Filter a list of agent records based on the provided filters.
    """
    if not agents:
        return []
    return [agent for agent in agents if matches_filter(agent, filters)]