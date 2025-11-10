thonimport logging
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

from utils.helpers import try_int, try_float, normalize_whitespace

class ZillowParser:
    """
    Responsible for parsing Zillow HTML pages and extracting structured agent data.
    """

    def parse_search_results(self, html: str, limit: Optional[int] = None) -> List[str]:
        """
        Parse a Zillow agent search results page and return candidate profile URLs.
        This is intentionally generic and may need to be tuned for Zillow's markup.
        """
        soup = BeautifulSoup(html, "html.parser")
        urls: List[str] = []

        for link in soup.find_all("a", href=True):
            href = link["href"]
            if "/profile/" not in href:
                continue

            if href.startswith("http"):
                url = href
            else:
                # Fallback to main Zillow domain
                url = f"https://www.zillow.com{href}"

            if url not in urls:
                urls.append(url)
                logging.debug("Discovered profile URL: %s", url)

            if limit is not None and len(urls) >= int(limit):
                break

        logging.info("Parsed %d profile URLs from search results.", len(urls))
        return urls

    def parse_agent_profile(
        self,
        html: str,
        profile_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Parse a Zillow agent profile page and extract core fields.

        The function makes best-effort guesses using common Zillow patterns but
        is resilient to minor layout changes.
        """
        soup = BeautifulSoup(html, "html.parser")

        agent_name = self._extract_agent_name(soup)
        agency = self._extract_agency(soup)
        phone = self._extract_phone(soup)
        location = self._extract_location(soup)
        rating = self._extract_rating(soup)
        reviews = self._extract_reviews_count(soup)
        sales_listings = self._extract_sales_listings_count(soup)
        sold_listings = self._extract_sold_listings_count(soup)

        if not profile_url:
            profile_url = self._extract_profile_url(soup)

        agent = {
            "agentName": agent_name,
            "profileUrl": profile_url,
            "agency": agency,
            "phoneNumber": phone,
            "reviews": reviews,
            "salesListings": sales_listings,
            "soldListings": sold_listings,
            "location": location,
            "rating": rating,
        }

        logging.debug("Parsed agent profile: %s", agent)
        return agent

    @staticmethod
    def _extract_agent_name(soup: BeautifulSoup) -> Optional[str]:
        # Try meta tag first
        meta = soup.find("meta", attrs={"property": "og:title"})
        if meta and meta.get("content"):
            return normalize_whitespace(meta["content"])

        # Fallback to primary heading
        h1 = soup.find("h1")
        if h1:
            return normalize_whitespace(h1.get_text(strip=True))

        return None

    @staticmethod
    def _extract_profile_url(soup: BeautifulSoup) -> Optional[str]:
        meta = soup.find("meta", attrs={"property": "og:url"})
        if meta and meta.get("content"):
            return meta["content"]
        return None

    @staticmethod
    def _extract_agency(soup: BeautifulSoup) -> Optional[str]:
        # Common pattern: agency name appears near "Brokerage" or "Company"
        possible_labels = ["Brokerage", "Company", "Agency"]
        for label in possible_labels:
            label_el = soup.find(string=lambda t: t and label in t)
            if label_el and label_el.parent:
                sibling = label_el.parent.find_next("span")
                if sibling:
                    return normalize_whitespace(sibling.get_text(strip=True))

        # Generic fallback
        agency_el = soup.find("div", class_="agent-brokerage")
        if agency_el:
            return normalize_whitespace(agency_el.get_text(strip=True))

        return None

    @staticmethod
    def _extract_phone(soup: BeautifulSoup) -> Optional[str]:
        # Look for tel links
        tel_link = soup.find("a", href=lambda href: href and href.startswith("tel:"))
        if tel_link:
            text = tel_link.get_text(strip=True)
            if text:
                return text

        # Fallback: any element with "phone" in its class name
        phone_el = soup.find(
            lambda tag: tag.name in {"span", "div"} and tag.get("class") and any(
                "phone" in cls.lower() for cls in tag["class"]
            )
        )
        if phone_el:
            return normalize_whitespace(phone_el.get_text(strip=True))

        return None

    @staticmethod
    def _extract_location(soup: BeautifulSoup) -> Optional[str]:
        # Look for "location" or "address" hints
        location_el = soup.find(
            lambda tag: tag.name in {"span", "div"} and tag.get("class") and any(
                "location" in cls.lower() or "address" in cls.lower()
                for cls in tag["class"]
            )
        )
        if location_el:
            return normalize_whitespace(location_el.get_text(strip=True))

        # Fallback: look for text containing a comma (city, state pattern)
        for span in soup.find_all("span"):
            text = span.get_text(strip=True)
            if "," in text and any(char.isdigit() for char in text) is False:
                return normalize_whitespace(text)

        return None

    @staticmethod
    def _extract_rating(soup: BeautifulSoup) -> Optional[float]:
        # Try microdata ratingValue
        rating_el = soup.find(attrs={"itemprop": "ratingValue"})
        if rating_el and rating_el.get("content"):
            return try_float(rating_el["content"])

        # Look for text like "4.9 / 5"
        text_candidates = soup.find_all(string=lambda t: t and " / 5" in t)
        for text in text_candidates:
            number_part = text.split(" / 5", 1)[0].strip()
            rating = try_float(number_part)
            if rating is not None:
                return rating

        return None

    @staticmethod
    def _extract_reviews_count(soup: BeautifulSoup) -> Optional[int]:
        # Try microdata reviewCount
        reviews_el = soup.find(attrs={"itemprop": "reviewCount"})
        if reviews_el and reviews_el.get("content"):
            return try_int(reviews_el["content"])

        # Look for patterns like "124 Reviews"
        for text in soup.find_all(string=True):
            if not text:
                continue
            stripped = text.strip()
            if "review" in stripped.lower():
                parts = stripped.split()
                for part in parts:
                    value = try_int(part)
                    if value is not None:
                        return value

        return None

    @staticmethod
    def _extract_sales_listings_count(soup: BeautifulSoup) -> Optional[int]:
        # Very generic: look for text blocks near "for sale" or similar
        for text in soup.find_all(string=True):
            if not text:
                continue
            lower = text.lower()
            if "for sale" in lower or "active listings" in lower:
                parts = text.split()
                for part in parts:
                    value = try_int(part)
                    if value is not None:
                        return value
        return None

    @staticmethod
    def _extract_sold_listings_count(soup: BeautifulSoup) -> Optional[int]:
        # Very generic: look for text blocks near "sold" or "recently sold"
        for text in soup.find_all(string=True):
            if not text:
                continue
            lower = text.lower()
            if "sold" in lower:
                parts = text.split()
                for part in parts:
                    value = try_int(part)
                    if value is not None:
                        return value
        return None