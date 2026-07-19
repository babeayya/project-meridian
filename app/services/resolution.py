"""Entity resolution: free-text query → canonical company.

1. Local DB match (fast path, already-seen companies).
2. Parallel provider search fan-out (Yahoo + Alpha Vantage when keyed).
3. Candidates are grouped by normalized company name: the same company listed
   on several exchanges (AAPL / AAPL.TO / APC.DE) is ONE candidate whose
   representative listing is the home exchange, not many competitors.
4. Confident single winner → persist company + primary listing and return a
   `match`; otherwise return ranked `candidates` for the frontend to pick.
"""
import difflib
import re

import structlog

from app.providers.base import Capability, Region, SymbolCandidate
from app.providers.registry import ProviderRegistry
from app.repositories.company import CompanyRepository
from app.schemas.company import CompanyProfile, ResolveCandidate, ResolveResponse

log = structlog.get_logger(__name__)

LOCAL_CONFIDENCE_ACCEPT = 0.93
REMOTE_CONFIDENCE_ACCEPT = 0.60
AMBIGUITY_GAP = 0.15

REGION_COUNTRY = {Region.US: "US", Region.IN: "IN", Region.GLOBAL: "XX"}

# Home-market exchanges outrank foreign cross-listings of the same name group.
EXCHANGE_PRIORITY = {
    "NASDAQ": 0, "NYSE": 0, "NSE": 0,
    "NYSEARCA": 1, "AMEX": 1, "BSE": 1, "BATS": 2,
}
DEFAULT_EXCHANGE_PRIORITY = 5

_LEGAL_SUFFIXES = frozenset(
    "inc incorporated corp corporation ltd limited co company plc sa ag nv "
    "se oyj ab spa holdings holding group lp llc".split()
)


def _normalize_name(name: str) -> str:
    tokens = re.sub(r"[^a-z0-9 ]", " ", name.lower()).split()
    core = [t for t in tokens if t not in _LEGAL_SUFFIXES]
    return " ".join(core or tokens)


def _name_similarity(query: str, name: str) -> float:
    q, n = _normalize_name(query), _normalize_name(name)
    if not q or not n:
        return 0.0
    if q == n:
        return 1.0
    return difflib.SequenceMatcher(None, q, n).ratio()


class ResolutionService:
    def __init__(self, companies: CompanyRepository, registry: ProviderRegistry) -> None:
        self.companies = companies
        self.registry = registry

    async def resolve(self, query: str) -> ResolveResponse:
        query = query.strip()

        local = await self.companies.search_local(query)
        if local:
            top_company, top_score = local[0]
            second = local[1][1] if len(local) > 1 else 0.0
            if top_score >= LOCAL_CONFIDENCE_ACCEPT and top_score - second >= AMBIGUITY_GAP:
                log.info("resolved_locally", query=query, company=top_company.name)
                return ResolveResponse(match=CompanyProfile.model_validate(top_company))

        candidates = await self._remote_candidates(query)
        if not candidates:
            if local:  # weaker local hits are still better than nothing
                return ResolveResponse(candidates=[
                    ResolveCandidate(
                        company_id=c.id, name=c.name,
                        ticker=c.listings[0].ticker if c.listings else "",
                        exchange=c.listings[0].exchange if c.listings else "",
                        symbol=(c.listings[0].yahoo_symbol or "") if c.listings else "",
                        region=c.country, confidence=score, provider="local",
                    )
                    for c, score in local
                ])
            return ResolveResponse()

        best = candidates[0]
        gap = best.confidence - (candidates[1].confidence if len(candidates) > 1 else 0.0)
        if best.confidence >= REMOTE_CONFIDENCE_ACCEPT and gap >= AMBIGUITY_GAP:
            company = await self._persist(best)
            return ResolveResponse(match=CompanyProfile.model_validate(company))
        return ResolveResponse(candidates=candidates[:8])

    async def select(self, candidate: ResolveCandidate) -> CompanyProfile:
        """Persist a user-picked candidate from a prior ambiguous resolve."""
        company = await self._persist(candidate)
        return CompanyProfile.model_validate(company)

    async def _remote_candidates(self, query: str) -> list[ResolveCandidate]:
        results = await self.registry.call_all(
            Capability.SYMBOL_SEARCH, Region.GLOBAL, "search", query=query
        )

        # Group by normalized name; each group is one company across exchanges.
        groups: dict[str, list[tuple[SymbolCandidate, str, int]]] = {}
        for batch, provider in results:
            for rank, c in enumerate(batch):
                groups.setdefault(_normalize_name(c.name), []).append((c, provider, rank))

        out: list[ResolveCandidate] = []
        for members in groups.values():
            members.sort(key=lambda m: (
                EXCHANGE_PRIORITY.get(m[0].exchange.upper(), DEFAULT_EXCHANGE_PRIORITY),
                m[2],
            ))
            rep, provider, _ = members[0]

            name_score = max(_name_similarity(query, m[0].name) for m in members)
            ticker_hit = any(m[0].ticker.lower() == query.lower() for m in members)
            top_ranked = any(m[2] == 0 for m in members)
            confidence = max(name_score, 0.9 if ticker_hit else 0.0)
            if top_ranked:
                confidence = min(1.0, confidence + 0.1)

            out.append(ResolveCandidate(
                name=rep.name, ticker=rep.ticker.upper(), exchange=rep.exchange.upper(),
                symbol=rep.symbol, region=rep.region.value,
                confidence=round(confidence, 4), provider=provider,
            ))

        out.sort(key=lambda c: c.confidence, reverse=True)
        return out

    async def _persist(self, cand: ResolveCandidate):
        region = (
            Region(cand.region)
            if cand.region in Region._value2member_map_ else Region.GLOBAL
        )
        return await self.companies.create_with_listing(
            name=cand.name,
            country=REGION_COUNTRY.get(region, "XX"),
            ticker=cand.ticker,
            exchange=cand.exchange,
            yahoo_symbol=cand.symbol or None,
            currency=None,
        )
