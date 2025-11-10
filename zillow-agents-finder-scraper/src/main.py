thonimport argparse
import json
import logging
import os
from typing import Any, Dict, List

from utils.helpers import (
    load_json_file,
    save_json_file,
    setup_logging,
    load_settings,
)
from utils.http_client import HttpClient
from extractors.zillow_parser import ZillowParser
from extractors.filters import AgentFilter, filter_agents

def build_http_client(settings: Dict[str, Any]) -> HttpClient:
    base_url = settings.get("base_url", "https://www.zillow.com")
    timeout = settings.get("request_timeout", 10)
    max_retries = settings.get("max_retries", 3)
    backoff_factor = settings.get("retry_backoff_factor", 1)
    rate_limit_per_minute = settings.get("rate_limit_per_minute", 30)
    user_agent = settings.get("user_agent")

    return HttpClient(
        base_url=base_url,
        timeout=timeout,
        max_retries=max_retries,
        backoff_factor=backoff_factor,
        rate_limit_per_minute=rate_limit_per_minute,
        user_agent=user_agent,
    )

def _build_filters(filter_dict: Dict[str, Any]) -> AgentFilter:
    if not filter_dict:
        return AgentFilter()
    return AgentFilter.from_dict(filter_dict)

def _process_profile_query(
    http_client: HttpClient,
    parser: ZillowParser,
    query: Dict[str, Any],
) -> List[Dict[str, Any]]:
    profile_url = query.get("profileUrl")
    if not profile_url:
        logging.warning("Profile query missing 'profileUrl' field, skipping.")
        return []

    logging.info("Fetching profile: %s", profile_url)
    html = http_client.get_url(profile_url)
    if not html:
        return []

    agent = parser.parse_agent_profile(html, profile_url=profile_url)
    filters = _build_filters(query.get("filters", {}))
    filtered = filter_agents([agent], filters)
    return filtered

def _process_search_query(
    http_client: HttpClient,
    parser: ZillowParser,
    query: Dict[str, Any],
    base_url: str,
) -> List[Dict[str, Any]]:
    name = query.get("name")
    location = query.get("location")
    limit = query.get("limit")

    if not name and not query.get("screenName"):
        logging.warning("Search query missing 'name' or 'screenName', skipping.")
        return []

    # If we have a screen name, we can directly build a profile URL
    screen_name = query.get("screenName")
    if screen_name:
        profile_url = f"{base_url.rstrip('/')}/profile/{screen_name}"
        logging.info("Using screenName query, direct profile URL: %s", profile_url)
        return _process_profile_query(
            http_client, parser, {"profileUrl": profile_url, "filters": query.get("filters", {})}
        )

    # Name-based search
    search_path = "/agents/real-estate-agent-reviews/"
    params: Dict[str, Any] = {}
    if name:
        params["searchQuery"] = name
    if location:
        params["locationText"] = location

    logging.info("Searching agents by name='%s', location='%s'", name, location)
    html = http_client.get(search_path, params=params)
    if not html:
        return []

    profile_urls = parser.parse_search_results(html, limit=limit)
    logging.info("Found %d candidate profiles", len(profile_urls))

    agents: List[Dict[str, Any]] = []
    for url in profile_urls:
        try:
            logging.info("Fetching candidate profile: %s", url)
            agent_html = http_client.get_url(url)
            if not agent_html:
                continue
            agent = parser.parse_agent_profile(agent_html, profile_url=url)
            agents.append(agent)
        except Exception as exc:  # noqa: BLE001
            logging.exception("Error processing profile %s: %s", url, exc)

    filters = _build_filters(query.get("filters", {}))
    filtered_agents = filter_agents(agents, filters)
    if limit is not None:
        filtered_agents = filtered_agents[: int(limit)]
    return filtered_agents

def process_queries(
    queries: List[Dict[str, Any]],
    settings: Dict[str, Any],
) -> List[Dict[str, Any]]:
    setup_logging(settings.get("log_level", "INFO"))

    http_client = build_http_client(settings)
    parser = ZillowParser()

    results: List[Dict[str, Any]] = []
    base_url = settings.get("base_url", "https://www.zillow.com")

    for idx, query in enumerate(queries, start=1):
        logging.info("Processing query %d/%d: %s", idx, len(queries), json.dumps(query))

        qtype = query.get("type", "search")
        try:
            if qtype == "profile":
                agents = _process_profile_query(http_client, parser, query)
            else:
                agents = _process_search_query(http_client, parser, query, base_url)

            results.extend(agents)
        except KeyboardInterrupt:
            logging.warning("Interrupted by user.")
            break
        except Exception as exc:  # noqa: BLE001
            logging.exception("Error processing query %s: %s", query, exc)

    logging.info("Finished processing queries. Total agents: %d", len(results))
    return results

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Zillow Agents Finder - scrape agent data from Zillow."
    )
    default_input = os.path.join("data", "inputs.sample.json")
    default_output = os.path.join("data", "output.json")

    parser.add_argument(
        "-i",
        "--input",
        default=default_input,
        help=f"Path to input JSON file (default: {default_input})",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=default_output,
        help=f"Path to output JSON file (default: {default_output})",
    )
    parser.add_argument(
        "-s",
        "--settings",
        default=None,
        help="Optional path to settings.json (defaults to src/config/settings.json)",
    )
    return parser.parse_args()

def main() -> None:
    args = parse_args()

    if args.settings:
        settings_path = args.settings
    else:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        settings_path = os.path.join(current_dir, "config", "settings.json")

    settings = load_settings(settings_path)
    queries = load_json_file(args.input)

    if not isinstance(queries, list):
        raise ValueError("Input JSON must be a list of query objects.")

    agents = process_queries(queries, settings)
    save_json_file(args.output, agents)

if __name__ == "__main__":
    main()