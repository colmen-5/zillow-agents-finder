thonimport logging
import time
from typing import Any, Dict, Optional
from urllib.parse import urljoin

import requests

class HttpClient:
    """
    Lightweight HTTP client with retry and basic rate limiting support.
    """

    def __init__(
        self,
        base_url: str,
        timeout: int = 10,
        max_retries: int = 3,
        backoff_factor: int = 1,
        rate_limit_per_minute: int = 60,
        user_agent: Optional[str] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.rate_limit_per_minute = rate_limit_per_minute
        self.session = requests.Session()

        self.default_headers: Dict[str, str] = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Connection": "keep-alive",
        }
        if user_agent:
            self.default_headers["User-Agent"] = user_agent
        else:
            self.default_headers[
                "User-Agent"
            ] = "Mozilla/5.0 (compatible; ZillowAgentsFinder/1.0; +https://example.com)"

        # Used for naïve rate limiting
        self._last_request_ts: float = 0.0

    def _respect_rate_limit(self) -> None:
        if not self.rate_limit_per_minute:
            return
        min_interval = 60.0 / float(self.rate_limit_per_minute)
        now = time.time()
        elapsed = now - self._last_request_ts
        if elapsed < min_interval:
            sleep_for = min_interval - elapsed
            logging.debug("Rate limiting active, sleeping for %.2f seconds", sleep_for)
            time.sleep(sleep_for)

    def _request(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Optional[str]:
        full_headers = dict(self.default_headers)
        if headers:
            full_headers.update(headers or {})

        for attempt in range(1, self.max_retries + 1):
            self._respect_rate_limit()
            try:
                logging.debug(
                    "HTTP %s %s params=%s attempt=%d",
                    method,
                    url,
                    params,
                    attempt,
                )
                resp = self.session.request(
                    method=method.upper(),
                    url=url,
                    params=params,
                    headers=full_headers,
                    timeout=self.timeout,
                )
                self._last_request_ts = time.time()

                if 200 <= resp.status_code < 300:
                    return resp.text

                if 400 <= resp.status_code < 500:
                    logging.error(
                        "Client error from %s: %s %s",
                        url,
                        resp.status_code,
                        resp.reason,
                    )
                    return None

                logging.warning(
                    "Server error from %s: %s %s (attempt %d)",
                    url,
                    resp.status_code,
                    resp.reason,
                    attempt,
                )
            except requests.RequestException as exc:  # noqa: BLE001
                logging.warning("HTTP request failed (attempt %d): %s", attempt, exc)

            if attempt < self.max_retries:
                backoff = self.backoff_factor * (2 ** (attempt - 1))
                logging.debug("Backing off for %.2f seconds before retry", backoff)
                time.sleep(backoff)

        logging.error("Exhausted HTTP retries for %s", url)
        return None

    def get(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Optional[str]:
        """
        Perform an HTTP GET relative to the configured base_url.
        """
        url = urljoin(self.base_url + "/", path.lstrip("/"))
        return self._request("GET", url, params=params, headers=headers)

    def get_url(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Optional[str]:
        """
        Perform an HTTP GET to an absolute URL.
        """
        return self._request("GET", url, params=params, headers=headers)