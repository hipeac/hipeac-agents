"""URL canonicalization shared by the service layer and the gates.

Two links that differ only in per-send tracking parameters or encoding are
the same page for caching and deduplication.
"""

import re
from urllib.parse import parse_qs, parse_qsl, unquote, urlencode, urlsplit, urlunsplit

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
    "_hsmi",
    "_hsenc",
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_content",
    "utm_term",
}


# Newsletter click-trackers and "view in browser" pages: they stand in front
# of the story (or of the whole email), never are it. Brevo redirects with a
# meta refresh, so a plain redirect-following request stops on its page.
_LINK_WRAPPERS = re.compile(
    r"""^https?://(?:
        [^/]*\.sp1-brevo\.net/
      | [^/]*\.list-manage\.com/track/
      | substack\.com/redirect/
      | t\.e2ma\.net/click/
      | click\.[^/]+/
      | email\.[^/]+/
      | [^/]+/ViewMessage\.do
      | (?:www\.)?google\.[a-z.]+/url\?
    )""",
    re.IGNORECASE | re.VERBOSE,
)
# A link that ends on one of these is no story: an image, or an error page a
# dead article redirected to (``finance.yahoo.com/?err=404``).
_NOT_A_PAGE = re.compile(r"\.(?:jpe?g|png|gif|webp|svg)(?:$|\?)|[?&]err=40\d", re.IGNORECASE)


def is_link_wrapper(url: str) -> bool:
    """Tell whether a URL is a newsletter's click-tracker or web view, in front of the story.

    :param url: The URL to check.
    :returns: ``True`` for a wrapper that must be resolved before it can be recorded.
    """
    return bool(_LINK_WRAPPERS.match(url.strip()))


def is_story_url(url: str) -> bool:
    """Tell whether a URL can stand as a finding's link: no wrapper, image or error page.

    :param url: The URL to check.
    :returns: ``True`` when the URL may be recorded.
    """
    return bool(url) and not is_link_wrapper(url) and not _NOT_A_PAGE.search(url)


def unwrap_query_redirect(url: str) -> str | None:
    """Read the destination a redirect link carries in its query (``google.com/url?q=…``).

    :param url: The URL to unwrap.
    :returns: The destination, or ``None`` when the URL carries none.
    """
    parts = urlsplit(url.strip())
    if not re.fullmatch(r"(?:www\.)?google\.[a-z.]+", parts.netloc) or parts.path != "/url":
        return None
    target = parse_qs(parts.query).get("q") or parse_qs(parts.query).get("url")
    return unquote(target[0]) if target and target[0].startswith(("http://", "https://")) else None


def strip_tracking(url: str) -> str:
    """Drop per-send tracking parameters from a URL, leaving every other byte as it was.

    :param url: The URL to clean.
    :returns: The URL without ``TRACKING_PARAMS``.
    """
    scheme, netloc, path, query, fragment = urlsplit(url.strip())
    kept = [part for part in query.split("&") if part and unquote(part.split("=", 1)[0]).lower() not in TRACKING_PARAMS]
    if len(kept) == len([part for part in query.split("&") if part]):
        return url.strip()
    return urlunsplit((scheme, netloc, path, "&".join(kept), fragment))


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
