"""GDELT DOC 2.0 adapter — free, no key, deep historical news reach.
Captures wire-service coverage (incl. Reuters-sourced stories) via domain
metadata since no free direct Reuters API exists."""
from datetime import UTC, datetime

from app.core.control import RateLimit
from app.providers.base import Capability, NewsItemDTO, ProviderAdapter, Region

DOC_URL = "https://api.gdeltproject.org/api/v2/doc/doc"


class GdeltAdapter(ProviderAdapter):
    name = "gdelt"
    capabilities = frozenset({Capability.NEWS})
    regions = frozenset({Region.GLOBAL})
    rate_limit = RateLimit(per_minute=10, per_day=1000)

    async def news(self, query: str, company_name: str,
                   lookback_days: int) -> list[NewsItemDTO]:
        span = f"{min(lookback_days, 90)}d"  # GDELT timespan cap for ArtList
        q = f'"{company_name}" sourcelang:english'
        data = await self.http.get_json(
            DOC_URL,
            params={"query": q, "mode": "ArtList", "format": "json",
                    "maxrecords": 50, "timespan": span, "sort": "DateDesc"},
        )
        out = []
        for a in data.get("articles", []):
            if not a.get("url") or not a.get("title"):
                continue
            published = None
            seen = a.get("seendate")  # "20260709T120000Z"
            if seen:
                try:
                    published = datetime.strptime(seen, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
                except ValueError:
                    published = None
            out.append(NewsItemDTO(
                url=a["url"], headline=a["title"], outlet=a.get("domain"),
                published_at=published, language=a.get("language", "en")[:8],
            ))
        return out


class NewsApiAdapter(ProviderAdapter):
    """NewsAPI.org — richer summaries; free tier 100 req/day, key required."""
    name = "newsapi"
    capabilities = frozenset({Capability.NEWS})
    regions = frozenset({Region.GLOBAL})
    rate_limit = RateLimit(per_minute=5, per_day=95)

    def __init__(self, http, api_key: str) -> None:  # type: ignore[no-untyped-def]
        super().__init__(http)
        self.api_key = api_key

    async def news(self, query: str, company_name: str,
                   lookback_days: int) -> list[NewsItemDTO]:
        data = await self.http.get_json(
            "https://newsapi.org/v2/everything",
            params={"q": f'"{company_name}"', "language": "en",
                    "sortBy": "publishedAt", "pageSize": 50},
            headers={"X-Api-Key": self.api_key},
        )
        out = []
        for a in data.get("articles", []):
            if not a.get("url") or not a.get("title"):
                continue
            published = None
            if a.get("publishedAt"):
                try:
                    published = datetime.fromisoformat(
                        a["publishedAt"].replace("Z", "+00:00"))
                except ValueError:
                    published = None
            out.append(NewsItemDTO(
                url=a["url"], headline=a["title"],
                summary=a.get("description"),
                outlet=(a.get("source") or {}).get("name"),
                published_at=published, language="en",
            ))
        return out
