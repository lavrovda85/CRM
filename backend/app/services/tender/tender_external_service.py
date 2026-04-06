"""Fetch tender-related pages from the public internet and search for tender links.

Используется MCP-инструментами и AI-ассистентом: разбор страницы по URL,
поиск кандидатов (DuckDuckGo). Защита от SSRF — блокировка приватных адресов
(если не включён dev-флаг в настройках).
"""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import os
import re
import shutil
import socket
import tempfile
from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from urllib.parse import parse_qs, urlencode, urlparse

import httpx
from bs4 import BeautifulSoup

from app.core.config import get_settings
from app.core.exceptions import ValidationError
from .tender_deadline_parse import extract_application_deadline_utc_from_html
from .tender_notice_fields import (
    build_notice_description_line,
    extract_zakupki_notice_fields,
    merge_zakupki_notice_fields_from_cache,
)
from .tender_preview_cache import get_tender_preview, store_tender_preview
from .tender_search_query import normalize_eis_search_query
from .tender_zakupki_urls import (
    canonical_zakupki_notice_url,
    extract_notice_segment_from_zakupki_html,
    extract_reg_number_from_zakupki_html,
    reg_number_from_zakupki_url,
    zakupki_common_info_url,
)

logger = logging.getLogger(__name__)

_MAX_EIS_SEARCH_PAGES = 10

_USER_AGENT = (
    "SPEC-CRM-TenderBot/1.0 (+https://example.local; tender import; contact: admin)"
)
# ЕИС / zakupki often return 403 to non-browser clients; use for HTML search + fragile pages.
_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


def _normalize_url_for_search_dedup(url: str) -> str:
    """Normalize notice URL so the same procurement is not listed twice (canonical zakupki).

    Uses registry number when present so ``printForm`` and ``ea20`` paths dedupe identically.
    """
    u = (url or "").strip()
    if not u:
        return u
    if "zakupki.gov.ru" not in u.lower():
        return u
    reg = reg_number_from_zakupki_url(u)
    if reg:
        return canonical_zakupki_notice_url(zakupki_common_info_url(reg, "ea20"))
    return canonical_zakupki_notice_url(u)


def _exclude_url_set(exclude_urls: list[str] | None) -> set[str]:
    """Build a set of normalized URLs to skip in merged search results."""
    out: set[str] = set()
    if not exclude_urls:
        return out
    for u in exclude_urls:
        nu = _normalize_url_for_search_dedup(str(u))
        if nu:
            out.add(nu)
    return out


def _normalize_url(raw: str) -> str:
    """Strip and validate http(s) URL string."""
    s = (raw or "").strip()
    if not s:
        raise ValidationError("url", "URL must be non-empty")
    parsed = urlparse(s)
    if parsed.scheme not in ("http", "https"):
        raise ValidationError("url", "Only http and https URLs are allowed")
    if not parsed.netloc:
        raise ValidationError("url", "URL must include a host")
    settings = get_settings()
    if parsed.scheme == "http" and not settings.tender_fetch_allow_insecure_http:
        raise ValidationError("url", "Only https:// is allowed (set TENDER_FETCH_ALLOW_INSECURE_HTTP=1 for http)")
    return s


def _reject_obvious_bad_host(hostname: str) -> None:
    """Block localhost and literal private IPs (no network I/O)."""
    settings = get_settings()
    if settings.tender_fetch_allow_private_hosts:
        return
    host = hostname.strip().lower()
    if host in ("localhost",) or host.endswith(".localhost"):
        raise ValidationError("url", "Host localhost is not allowed for tender fetch")
    try:
        ipaddress.ip_address(host)
        is_literal_ip = True
    except ValueError:
        is_literal_ip = False
    if is_literal_ip:
        ip = ipaddress.ip_address(host)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise ValidationError("url", "Private or non-public IP addresses are not allowed")


def _ip_is_public(addr: str) -> bool:
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return False
    return not (
        ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast
    )


async def _doh_resolve_ipv4(hostname: str) -> str:
    """Resolve A record via Cloudflare DNS-over-HTTPS to literal 1.1.1.1 (no local DNS lookup).

    Works when the container cannot use system resolvers but outbound HTTPS to 1.1.1.1 is allowed.
    """
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(20.0), verify=True) as client:
            r = await client.get(
                "https://1.1.1.1/dns-query",
                params={"name": hostname, "type": "A"},
                headers={"accept": "application/dns-json"},
            )
            r.raise_for_status()
            data = r.json()
    except httpx.HTTPError as exc:
        raise ValidationError("url", f"DNS-over-HTTPS resolution failed: {exc!s}") from exc

    for ans in data.get("Answer") or []:
        if ans.get("type") != 1:
            continue
        raw = ans.get("data")
        if not raw or not isinstance(raw, str):
            continue
        candidate = raw.strip().split()[0] if raw else ""
        if candidate and _ip_is_public(candidate):
            return candidate

    raise ValidationError(
        "url",
        "Could not obtain a public IPv4 address for this host via DNS-over-HTTPS.",
    )


async def _fetch_strategy(
    hostname: str,
) -> tuple[Literal["httpx"], None] | tuple[Literal["curl"], str]:
    """Decide whether normal httpx can be used or curl --resolve with DoH IP."""
    settings = get_settings()
    _reject_obvious_bad_host(hostname)
    if settings.tender_fetch_allow_private_hosts:
        return ("httpx", None)

    host = hostname.strip().lower()
    try:
        ipaddress.ip_address(host)
        return ("httpx", None)
    except ValueError:
        pass

    loop = asyncio.get_running_loop()

    def _system_resolve() -> tuple[list[str], bool]:
        """Return (public_ips, had_any_ip_from_system)."""
        try:
            infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
        except socket.gaierror:
            return [], False
        public: list[str] = []
        any_seen = False
        for _fam, _typ, _proto, _canon, sockaddr in infos:
            addr = sockaddr[0]
            if not isinstance(addr, str):
                continue
            any_seen = True
            if _ip_is_public(addr):
                public.append(addr)
        return public, any_seen

    public_addrs, had_any = await loop.run_in_executor(None, _system_resolve)
    if public_addrs:
        return ("httpx", None)
    if had_any:
        raise ValidationError(
            "url",
            "Host resolves only to non-public (private/link-local) addresses, which are not allowed.",
        )

    if not settings.tender_fetch_doh_fallback:
        raise ValidationError(
            "url",
            "DNS lookup failed. Set dns on the backend service in docker-compose, or enable "
            "TENDER_FETCH_DOH_FALLBACK=true (default) and ensure HTTPS to 1.1.1.1 is allowed.",
        )

    ip = await _doh_resolve_ipv4(host)
    if not _ip_is_public(ip):
        raise ValidationError("url", f"DNS-over-HTTPS returned a non-public address: {ip}")
    if shutil.which("curl") is None:
        raise ValidationError(
            "url",
            "System DNS failed and `curl` was not found. Install curl in the image or fix container DNS.",
        )
    return ("curl", ip)


def _detect_source_label(url: str) -> str | None:
    """Best-effort platform label from hostname."""
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return None
    if "zakupki.gov.ru" in host:
        return "zakupki.gov.ru"
    if "roseltorg.ru" in host:
        return "roseltorg.ru"
    if "etpgpb.ru" in host or "etp.gpb.ru" in host:
        return "ETP GPB"
    if "fabrikant.ru" in host:
        return "fabrikant.ru"
    if "sberbank-ast.ru" in host:
        return "sberbank-ast.ru"
    return host[:80] if host else None


def _strip_noise(text: str, max_len: int = 8000) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_len:
        return text[: max_len - 1] + "…"
    return text


def _extract_from_html(html: str, page_url: str) -> dict[str, str | None]:
    """Parse HTML for title, description, and truncated body text."""
    soup = BeautifulSoup(html, "lxml")

    title: str | None = None
    og = soup.find("meta", property="og:title")
    if og and og.get("content"):
        title = str(og["content"]).strip()
    if not title:
        t = soup.find("title")
        if t and t.string:
            title = str(t.string).strip()

    description: str | None = None
    ogd = soup.find("meta", property="og:description")
    if ogd and ogd.get("content"):
        description = str(ogd["content"]).strip()
    if not description:
        for m in soup.find_all("meta"):
            if (m.get("name") or "").lower() == "description" and m.get("content"):
                description = str(m["content"]).strip()
                break

    # Main text: prefer article/main, else body stripped scripts/styles
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    main = soup.find("main") or soup.find("article") or soup.find("body")
    body_text = ""
    if main:
        body_text = _strip_noise(main.get_text(separator=" ", strip=True), 6000)

    if not description and body_text:
        description = _strip_noise(body_text, 500)

    return {
        "title": title or None,
        "description": description or None,
        "text_excerpt": body_text or None,
        "source_guess": _detect_source_label(page_url),
    }


@dataclass(frozen=True)
class FetchedTenderPage:
    """Structured result of fetching a single tender-related URL."""

    url: str
    final_url: str
    http_status: int
    title: str | None
    description: str | None
    text_excerpt: str | None
    source_guess: str | None
    content_type: str | None
    application_deadline_utc: datetime | None = None
    notice_fields: dict[str, str] | None = None


async def _curl_download_resolved(
    url: str,
    hostname: str,
    resolved_ip: str,
    port: int,
    max_bytes: int,
    timeout_s: float,
    *,
    request_headers: dict[str, str] | None = None,
) -> tuple[bytes, int, str, str | None]:
    """GET URL using curl --resolve (bypasses broken container DNS for the target host)."""
    hdrs = dict(request_headers or {})
    ua = hdrs.pop("User-Agent", _USER_AGENT)
    accept = hdrs.pop("Accept", "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8")
    fd, path = tempfile.mkstemp(prefix="tnd_", suffix=".bin")
    os.close(fd)
    try:
        to_s = str(max(5, int(timeout_s)))
        cmd: list[str] = [
            "curl",
            "-sS",
            "-L",
            "--max-time",
            to_s,
            "--max-filesize",
            str(max_bytes),
            "-A",
            ua,
            "-H",
            f"Accept: {accept}",
        ]
        for hk, hv in hdrs.items():
            cmd.extend(["-H", f"{hk}: {hv}"])
        cmd.extend(
            [
                "--resolve",
                f"{hostname}:{port}:{resolved_ip}",
                "-o",
                path,
                "-w",
                "%{http_code}\\n%{url_effective}",
                url,
            ]
        )
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await proc.communicate()
        if proc.returncode != 0:
            msg = (err.decode("utf-8", errors="replace") or out.decode("utf-8", errors="replace")).strip()
            raise ValidationError("url", f"curl failed (exit {proc.returncode}): {msg or 'unknown error'}")
        meta = out.decode("utf-8", errors="replace").strip().split("\n", 1)
        code_raw = (meta[0] or "").strip()
        final_url = (meta[1] or "").strip() if len(meta) > 1 else ""
        if not final_url:
            final_url = url
        try:
            status = int(code_raw)
        except ValueError:
            status = 502
        with open(path, "rb") as f:
            raw = f.read()
        ctype: str | None = "text/html"
        return raw, status, final_url, ctype
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


async def _http_get_bytes(
    normalized_url: str,
    request_headers: dict[str, str],
) -> tuple[bytes, int, str, str | None]:
    """GET URL and return raw body, status, final URL, content-type (same transport as tender fetch)."""
    parsed = urlparse(normalized_url)
    host = parsed.hostname or ""
    if not host:
        raise ValidationError("url", "URL must include a valid host")

    strategy = await _fetch_strategy(host)
    settings = get_settings()
    timeout = httpx.Timeout(settings.tender_fetch_timeout_seconds)
    limits = httpx.Limits(max_connections=5)
    max_b = settings.tender_fetch_max_bytes
    port = parsed.port or (443 if parsed.scheme == "https" else 80)

    if strategy[0] == "httpx":
        try:
            async with httpx.AsyncClient(timeout=timeout, limits=limits, follow_redirects=True) as client:
                async with client.stream("GET", normalized_url, headers=request_headers) as resp:
                    chunks: list[bytes] = []
                    total = 0
                    async for chunk in resp.aiter_bytes():
                        chunks.append(chunk)
                        total += len(chunk)
                        if total > max_b:
                            raise ValidationError("url", f"Response exceeds maximum size ({max_b} bytes)")
                    raw = b"".join(chunks)
                    status = resp.status_code
                    final_url = str(resp.url)
                    ctype = resp.headers.get("content-type")
                    return raw, status, final_url, ctype
        except httpx.HTTPError as exc:
            logger.warning("HTTP GET failed for %s: %s", normalized_url, exc)
            hint = ""
            err = exc.__cause__ or exc
            if isinstance(err, OSError) and (
                getattr(err, "errno", None) in (-3, 11001, 11002)
                or "name resolution" in str(err).lower()
                or "getaddrinfo" in str(err).lower()
            ):
                hint = (
                    " (DNS/network: ensure the backend container can resolve public hostnames — "
                    "set dns: [8.8.8.8, 1.1.1.1] on the backend service in Docker Compose.)"
                )
            raise ValidationError("url", f"Failed to fetch URL: {exc!s}{hint}") from exc

    assert strategy[0] == "curl"
    resolved_ip = strategy[1]
    assert resolved_ip is not None
    return await _curl_download_resolved(
        normalized_url,
        host,
        resolved_ip,
        port,
        max_b,
        settings.tender_fetch_timeout_seconds,
        request_headers=request_headers,
    )


async def tender_http_get(
    url: str,
    *,
    browser_headers: bool = True,
) -> tuple[bytes, int, str, str | None]:
    """GET a URL using the same transport stack as ``fetch_tender_page`` (for file downloads).

    Args:
        url: https (or http if allowed) URL.
        browser_headers: Use browser-like User-Agent (recommended for zakupki filestore).

    Returns:
        Raw body, HTTP status, final URL, content-type.
    """
    normalized = _normalize_url(url)
    headers: dict[str, str] = {"Accept": "*/*"}
    if browser_headers:
        headers["User-Agent"] = _BROWSER_UA
    return await _http_get_bytes(normalized, headers)


async def fetch_tender_page(url: str) -> FetchedTenderPage:
    """Download URL and extract metadata and text excerpt (best effort).

    Args:
        url: Public https (or http if allowed) page with tender information.

    Returns:
        FetchedTenderPage with parsed fields.

    Raises:
        ValidationError: Invalid URL or blocked host.
        ValidationError: On network/HTTP failures (wrapped).
    """
    normalized = _normalize_url(url)
    normalized = canonical_zakupki_notice_url(normalized)
    headers = {"User-Agent": _USER_AGENT, "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8"}
    host_l = (urlparse(normalized).hostname or "").lower()
    if "zakupki.gov.ru" in host_l:
        headers["User-Agent"] = _BROWSER_UA
    raw, status, final_url, ctype = await _http_get_bytes(normalized, headers)

    if status >= 400:
        logger.warning("tender fetch HTTP %s for %s", status, normalized)

    text = raw.decode("utf-8", errors="replace")
    if "html" not in (ctype or "").lower() and not text.lstrip().lower().startswith("<!doctype html"):
        # Still try to parse; some servers omit Content-Type
        pass

    # If the URL had no regNumber but the body contains one (redirect / landing page), fetch common-info once.
    try:
        host_l = (urlparse(final_url).hostname or "").lower()
        if "zakupki.gov.ru" in host_l:
            fq = parse_qs(urlparse(final_url).query)
            if not (fq.get("regNumber") or [None])[0]:
                reg = extract_reg_number_from_zakupki_html(text)
                seg = extract_notice_segment_from_zakupki_html(text) or "ea20"
                if reg:
                    candidate = canonical_zakupki_notice_url(zakupki_common_info_url(reg, seg))
                    base = final_url.split("#", 1)[0]
                    if candidate.rstrip("/") != base.rstrip("/"):
                        try:
                            raw2, status2, final_url2, ctype2 = await _http_get_bytes(candidate, headers)
                            if status2 < 500 and len(raw2) > 500:
                                raw, status, final_url, ctype = raw2, status2, final_url2, ctype2
                                text = raw.decode("utf-8", errors="replace")
                        except ValidationError:
                            pass
    except Exception:
        pass

    extracted = _extract_from_html(text, final_url)
    deadline_utc = extract_application_deadline_utc_from_html(text)
    notice_map: dict[str, str] | None = None
    title_out = extracted["title"]
    desc_out = extracted["description"]
    if "zakupki.gov.ru" in (final_url or "").lower():
        zf = extract_zakupki_notice_fields(text)
        canon = canonical_zakupki_notice_url(final_url)
        cached_preview = get_tender_preview(canon)
        if cached_preview and isinstance(cached_preview.get("notice_fields"), dict):
            merge_zakupki_notice_fields_from_cache(zf, cached_preview["notice_fields"])
        if deadline_utc is None and cached_preview:
            raw_dl = cached_preview.get("application_deadline_utc")
            if isinstance(raw_dl, str) and raw_dl.strip():
                try:
                    deadline_utc = datetime.fromisoformat(raw_dl.replace("Z", "+00:00"))
                except ValueError:
                    pass
        notice_map = zf.to_public_dict() or None
        if zf.subject and zf.subject.strip():
            title_out = zf.subject.strip()[:1000]
        line = build_notice_description_line(zf)
        if line:
            desc_out = line[:4000]

    page = FetchedTenderPage(
        url=normalized,
        final_url=final_url,
        http_status=status,
        title=title_out,
        description=desc_out,
        text_excerpt=extracted["text_excerpt"],
        source_guess=extracted["source_guess"],
        content_type=ctype,
        application_deadline_utc=deadline_utc,
        notice_fields=notice_map,
    )
    try:
        store_tender_preview(
            canonical_zakupki_notice_url(final_url),
            {
                "final_url": final_url,
                "title": page.title,
                "description": page.description,
                "notice_fields": notice_map,
                "application_deadline_utc": deadline_utc.isoformat() if deadline_utc else None,
            },
        )
    except Exception:
        pass
    return page


def _parse_zakupki_extended_search_html(html: str, max_results: int) -> list[dict[str, str]]:
    """Extract notice links from zakupki.gov.ru extended search results HTML."""
    soup = BeautifulSoup(html, "lxml")
    base = "https://zakupki.gov.ru"
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for a in soup.find_all("a", href=True):
        href = str(a.get("href") or "").strip()
        if "/epz/order/notice/" not in href:
            continue
        if href.startswith("//"):
            full = "https:" + href
        elif href.startswith("/"):
            full = base + href
        elif href.startswith("http"):
            full = href
        else:
            continue
        full = full.split("#", 1)[0]
        full = canonical_zakupki_notice_url(full)
        if full in seen:
            continue
        seen.add(full)
        title = (a.get_text(separator=" ", strip=True) or full)[:500]
        out.append(
            {
                "title": title,
                "url": full[:2000],
                "snippet": "ЕИС zakupki.gov.ru — расширенный поиск",
            }
        )
        if len(out) >= max_results:
            break
    return out


async def _zakupki_extended_search(
    query: str,
    max_results: int,
    *,
    page_number: int = 1,
) -> list[dict[str, str]]:
    """Query ЕИС extended search HTML (primary source; DDG often misses or returns empty)."""
    per_page = min(max(10, max_results), 50)
    page = max(1, int(page_number))
    params = {
        "searchString": query,
        "morphology": "on",
        "pageNumber": str(page),
        "sortDirection": "false",
        "recordsPerPage": f"_{per_page}",
        "showLotsInfoHidden": "false",
        "sortBy": "UPDATE_DATE",
    }
    qs = urlencode(params, safe="_")
    search_url = f"https://zakupki.gov.ru/epz/order/extendedsearch/results.html?{qs}"
    headers = {
        "User-Agent": _BROWSER_UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://zakupki.gov.ru/epz/order/extendedsearch/results.html",
    }
    try:
        raw, status, _final, _ctype = await _http_get_bytes(search_url, headers)
    except ValidationError:
        logger.warning("zakupki EIS search request failed for query=%s", query[:120])
        return []
    except Exception as exc:
        logger.warning("zakupki EIS search error: %s", exc)
        return []
    if status >= 400:
        logger.warning("zakupki EIS search HTTP status %s", status)
        return []
    html = raw.decode("utf-8", errors="replace")
    low = html.lower()
    if "captcha" in low or "доступ ограничен" in low or "access denied" in low:
        logger.warning("zakupki EIS search page may be blocking automated access")
        return []
    return _parse_zakupki_extended_search_html(html, max_results)


def _run_ddg_text(query: str, max_results: int) -> list[dict[str, str]]:
    """Synchronous DuckDuckGo text search (run in thread pool)."""
    try:
        from duckduckgo_search import DDGS
    except ImportError as exc:  # pragma: no cover
        raise ValidationError("search", "duckduckgo-search package is not installed") from exc

    out: list[dict[str, str]] = []
    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=max_results):
            href = (r.get("href") or r.get("url") or "").strip()
            if not href:
                continue
            if not href.startswith("http"):
                continue
            out.append(
                {
                    "title": (r.get("title") or "")[:500],
                    "url": href[:2000],
                    "snippet": (r.get("body") or "")[:1200],
                }
            )
            if len(out) >= max_results:
                break
    return out


async def search_tender_candidates(
    query: str,
    *,
    max_results: int | None = None,
    prefer_zakupki_gov: bool = False,
    enrich: bool = True,
    only_open_deadlines: bool | None = None,
    exclude_urls: list[str] | None = None,
) -> list[dict[str, str]]:
    """Search for tender notices: ЕИС HTML first, then DuckDuckGo (DDG alone is often empty for site:).

    Args:
        query: Keywords (e.g. product, region, OKPD2).
        max_results: Cap on results (default from settings).
        prefer_zakupki_gov: If True, also run a DDG query with ``site:zakupki.gov.ru`` after others.
        enrich: If True, fetch pages and add Russian ``summary`` (optional AI when key is set).
        only_open_deadlines: If True (default from settings), drop tenders whose parsed submission
            deadline is before server UTC time. Ignored when ``enrich`` is False.
        exclude_urls: Notice URLs already shown to the user (normalized); skipped; ЕИС is queried
            across multiple pages until enough new rows are collected or pages run out.

    Returns:
        List of dicts with keys title, url, snippet, and when enrich is True: ``summary``,
        optional ``submission_deadline_utc`` (ISO-8601).
    """
    settings = get_settings()
    lim = max_results if max_results is not None else settings.tender_search_max_results
    lim = max(1, min(int(lim), 50))
    q = (query or "").strip()
    if not q:
        raise ValidationError("query", "Search query must be non-empty")

    q_search, exclusion_tokens = normalize_eis_search_query(q)
    if not (q_search or "").strip():
        q_search = q

    merged: list[dict[str, str]] = []
    seen: set[str] = set(_exclude_url_set(exclude_urls))

    def _add(items: list[dict[str, str]]) -> None:
        for it in items:
            u = (it.get("url") or "").strip()
            if not u:
                continue
            nu = _normalize_url_for_search_dedup(u)
            if nu in seen:
                continue
            seen.add(nu)
            merged.append(it)
            if len(merged) >= lim:
                return

    # 1) Прямой поиск по ЕИС — несколько страниц, пока не наберём lim новых ссылок
    page = 1
    while len(merged) < lim and page <= _MAX_EIS_SEARCH_PAGES:
        need = lim - len(merged)
        fetch_n = min(50, max(need * 3, 20))
        try:
            eis = await _zakupki_extended_search(q_search, fetch_n, page_number=page)
        except Exception as exc:
            logger.warning("zakupki extended search raised: %s", exc)
            eis = []
        if not eis:
            break
        _add(eis)
        page += 1

    # 2) DDG без site: — шире охват
    remaining = lim - len(merged)
    if remaining > 0:
        try:
            ddg_broad = await asyncio.to_thread(_run_ddg_text, q_search, remaining)
            _add(ddg_broad)
        except Exception as exc:
            logger.warning("DDG broad search failed: %s", exc)

    # 3) Опционально: DDG с site:zakupki.gov.ru (доп. к ЕИС)
    remaining = lim - len(merged)
    if remaining > 0 and prefer_zakupki_gov:
        try:
            ddg_site = await asyncio.to_thread(
                _run_ddg_text,
                f"site:zakupki.gov.ru {q_search}",
                remaining,
            )
            _add(ddg_site)
        except Exception as exc:
            logger.warning("DDG site: search failed: %s", exc)

    # 4) Если ничего не нашлось, повтор с исходной фразой (редко помогает DDG)
    if not merged and q_search != q:
        try:
            eis2 = await _zakupki_extended_search(q, lim)
            _add(eis2)
        except Exception as exc:
            logger.warning("zakupki extended search retry raised: %s", exc)
        remaining = lim - len(merged)
        if remaining > 0:
            try:
                ddg_broad = await asyncio.to_thread(_run_ddg_text, q, remaining)
                _add(ddg_broad)
            except Exception as exc:
                logger.warning("DDG broad retry failed: %s", exc)

    result = merged[:lim]
    if enrich:
        from .tender_search_enrich_service import enrich_tender_search_results

        oo = (
            settings.tender_search_only_open_deadlines
            if only_open_deadlines is None
            else only_open_deadlines
        )
        return await enrich_tender_search_results(
            result,
            only_open_deadlines=oo,
            exclusion_tokens=exclusion_tokens,
        )
    return result
