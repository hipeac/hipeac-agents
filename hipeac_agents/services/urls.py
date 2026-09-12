"""URL canonicalization shared by the service layer and the gates.

Two links that differ only in per-send tracking parameters or encoding are
the same page for caching and deduplication.
"""

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from w3lib.url import canonicalize_url


# Query parameters that only ever carry per-send tracking state; two links
# that differ solely in these are the same page for cache and dedupe.
TRACKING_PARAMS = {
    "gclid",
    "fbclid",
    "mc_eid",
    "mc_cid",
    "mkt_tok",
    "jsessionid",
    "ck_subscriber_id",
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_content",
    "utm_term",
}


def display_domain(url: str) -> str:
    """Return a URL's bare domain, for use as link text instead of a raw URL.

    :param url: The URL to render.
    :returns: The domain without a leading ``www.``; the URL itself when it has no host.
    """
    host = urlsplit(url).netloc
    return host.removeprefix("www.") if host else url


def normalize_url(url: str) -> str:
    """Return the canonical form of a URL for caching and deduplication.

    :param url: The URL as it appears in the source.
    :returns: The canonical URL for identity purposes; empty input gives ``""``.
    """
    if not url:
        return ""

    canonical = canonicalize_url(url.strip())
    scheme, netloc, path, query, _fragment = urlsplit(canonical)
    pairs = [
        (key, value) for key, value in parse_qsl(query, keep_blank_values=True) if key.lower() not in TRACKING_PARAMS
    ]
    return urlunsplit((scheme, netloc, path, urlencode(sorted(pairs)), ""))
