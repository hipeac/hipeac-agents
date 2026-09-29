"""Judgement-free harvest gates and helpers.

Every function here is deterministic Python — unit-tested with no mocking, no
LLM. The LLM calls that need judgement live in ``context.py`` and only run
after these cheap checks.
"""

import re
from datetime import date

from hipeac_agents.agents.vision_watch import schemas
from hipeac_agents.agents.vision_watch.schemas import Finding, FindingsFile, RejectedItem


_DATE_IN_TEXT = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_META_REFRESH = re.compile(r"""http-equiv=["']?refresh["']?[^>]*?content=["'][^;"']*;\s*(?:url=)?([^"'>\s]+)""", re.I)
_URL_IN_TEXT = re.compile(r"https?://[^\s\)\>\"']+")


def http_url_is_dead(url: str) -> bool | None:
    """Check a URL cheaply, before paying a full scrape for it.

    A light HEAD via ``urllib``: a clean 404/410 means the link is dead — no
    Firecrawl needed. Ambiguous outcomes (bot walls, redirects, timeouts)
    return ``False`` — the caller falls through to the crawl provider.

    :param url: The candidate URL to check.
    :returns: ``True`` when the URL is certainly dead, else ``False``.
    """
    import urllib.error
    import urllib.request

    if not url.lower().startswith(("http://", "https://")):
        return False
    try:
        request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "hipeac-vision-watch/0.1"})  # noqa: S310 — http(s) schemes enforced above
        with urllib.request.urlopen(request, timeout=10):  # noqa: S310 — http(s) schemes enforced above
            return False
    except urllib.error.HTTPError as exc:
        return exc.code in (404, 410)
    except Exception:
        return False


def resolve_link(url: str, hops: int = 3) -> str:
    """Follow a newsletter's click-tracker to the page it stands for.

    A redirect that carries its destination (``google.com/url?q=…``) is read
    without a request; a plain ``urllib`` GET follows HTTP redirects; a tracker
    that answers with its own page and a meta refresh (Brevo) is followed from
    that page. A
    blocked destination (403 on a news site) still names its URL. Anything
    unexpected returns the last URL reached — the caller checks it with
    ``is_story_url``.

    :param url: The wrapped link.
    :param hops: How many wrappers to unwrap in a row.
    :returns: The destination URL, or the last one reached.
    """
    import urllib.error
    import urllib.request

    from hipeac_agents.services.urls import is_link_wrapper, unwrap_query_redirect

    for _ in range(hops):
        if target := unwrap_query_redirect(url):
            url = target
            continue
        if not url.lower().startswith(("http://", "https://")):
            return url
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (hipeac-vision-watch)"})  # noqa: S310 — http(s) schemes enforced above
            with urllib.request.urlopen(request, timeout=15) as response:  # noqa: S310 — http(s) schemes enforced above
                final, body = response.geturl(), response.read(65536).decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            return exc.geturl() or url
        except Exception:
            return url
        if not is_link_wrapper(final):
            return final
        refresh = _META_REFRESH.search(body)
        if refresh is None and unwrap_query_redirect(final) is None:
            return final
        url = refresh.group(1) if refresh else final
    return url


def build_due_list(catalog: schemas.SourceCatalog) -> list[schemas.SourceEntry]:
    """Build the list of sources due this run: every catalog source, every week.

    Skipped sources stay in the list, so they are reported (as blocked)
    rather than silently missing from the run summary.

    :param catalog: The parsed source catalog.
    :returns: The catalog's sources.
    """
    return list(catalog.sources)


def window_gate(item_date: date | None, window_start: date, window_end: date) -> bool:
    """Check the item is dated within the harvest window.

    :param item_date: The candidate's date, or ``None`` if unknown.
    :param window_start: Window start (Saturday).
    :param window_end: Window end (Friday).
    :returns: ``True`` when inside the window; unknown dates stay in.
    """
    if item_date is None:
        return True

    return window_start <= item_date <= window_end


def duplicate_gate(url: str, prior_findings: list[FindingsFile]) -> bool:
    """Check a URL's canonical form is not already recorded in recent findings.

    :param url: The candidate's URL.
    :param prior_findings: The recent findings files read for deduplication.
    :returns: ``True`` when the item is a duplicate and must be rejected.
    """
    known = {normalize_url(finding.url) for file in prior_findings for finding in file.findings}
    return normalize_url(url) in known


def normalize_url(url: str) -> str:
    """Return the canonical form of a URL for caching and deduplication.

    Thin re-export of :func:`hipeac_agents.services.urls.normalize_url` so
    the gates module keeps a single import surface.

    :param url: The URL as it appears in the source.
    :returns: The canonical URL for identity purposes.
    """
    from hipeac_agents.services.urls import normalize_url as _normalize

    return _normalize(url)


def parse_iso_date(text: str) -> date | None:
    """Extract the first ISO date from free text.

    :param text: Text such as a page body or newsletter item.
    :returns: The parsed date, or ``None`` when none found.
    """
    if match := _DATE_IN_TEXT.search(text or ""):
        try:
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            return None

    return None


def extract_links(text: str) -> list[str]:
    """Extract URLs from a newsletter or tip body.

    :param text: The message body.
    :returns: The URLs in order of first appearance, deduplicated.
    """
    seen: dict[str, None] = {}

    for match in _URL_IN_TEXT.finditer(text or ""):
        url = match.group(0).rstrip(".,;")
        seen.setdefault(url, None)

    return list(seen)


def headline_in_body(claimed_title: str, body: str) -> bool:
    """Check a headline appears in a newsletter body — the newsletter gate.

    Normalised comparison on alphanumeric characters only: email HTML→text
    conversion mangles punctuation (curly quotes, apostrophes), so everything
    non-alphanumeric is stripped before the case-folded substring check.

    :param claimed_title: The headline the newsletter surfaces.
    :param body: The newsletter text.
    :returns: ``True`` when the headline appears in the body.
    """
    normalise = lambda text: re.sub(r"[^a-z0-9]+", "", (text or "").casefold())  # noqa: E731
    return normalise(claimed_title) in normalise(body)


def pick_resample(findings: list[Finding], fraction: float = 0.2) -> list[Finding]:
    """Pick ~fraction of findings for a fresh re-sample fetch.

    :param findings: The verified findings.
    :param fraction: The re-sample fraction.
    :returns: The deterministic sample: every ``1//fraction``-th finding.
    """
    if not findings:
        return []

    stride = max(1, round(1 / fraction))
    return findings[::stride]


def find_id(week: str, ordinal: int) -> str:
    """Build a finding id like ``f-2026-W24-01``.

    :param week: The week label.
    :param ordinal: The 1-based ordinal within the week.
    :returns: The finding id.
    """
    return f"f-{week}-{ordinal:02d}"


def kept_findings(findings: list[Finding], drop_ids: set[str]) -> list[Finding]:
    """Return findings minus the dropped ids, preserving order.

    :param findings: All findings.
    :param drop_ids: Ids to remove.
    :returns: The kept findings.
    """
    return [finding for finding in findings if finding.id not in drop_ids]


def dedupe_rejects(rejected: list[RejectedItem]) -> list[RejectedItem]:
    """Deduplicate rejected items by URL, keeping the first.

    :param rejected: All rejected items collected this run.
    :returns: The deduplicated rejected items.
    """
    seen: dict[str, RejectedItem] = {}

    for item in rejected:
        seen.setdefault(item.url, item)

    return list(seen.values())
