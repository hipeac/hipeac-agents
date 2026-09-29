"""Unit tests for URL display/canonicalization helpers (no mocking)."""

import pytest

from hipeac_agents.services.urls import (
    display_domain,
    is_link_wrapper,
    is_story_url,
    strip_tracking,
    unwrap_query_redirect,
)


class TestDisplayDomain:
    def test_strips_www(self):
        assert display_domain("https://www.example.com/a/b?q=1") == "example.com"

    def test_keeps_bare_domain(self):
        assert display_domain("https://example.com/a") == "example.com"

    def test_keeps_subdomain_other_than_www(self):
        assert display_domain("https://blog.example.com/a") == "blog.example.com"

    def test_empty_url_returns_itself(self):
        assert display_domain("") == ""


class TestLinkWrappers:
    @pytest.mark.parametrize(
        "url",
        [
            "https://4ntll.r.sp1-brevo.net/mk/cl/f/sh/7nVU1aA2ng01/INRob",
            "https://substack.com/redirect/5ea89152-6f6b?j=eyJ1",
            "https://click.wtwhmedia.com/ViewMessage.do;jsessionid=E8BA73",
            "https://t.e2ma.net/click/j0skn1/njexzoie/f12p5aq",
            "https://email.sifted.eu/events/public/v1/encoded/track/tc/LZ",
            "https://example.us1.list-manage.com/track/click?u=1",
            "https://www.google.com/url?q=https%3A%2F%2Fexample.com%2Fa&sa=D",
        ],
    )
    def test_newsletter_trackers_and_web_views(self, url):
        assert is_link_wrapper(url)
        assert not is_story_url(url)

    @pytest.mark.parametrize(
        "url",
        [
            "https://ocpl.substack.com/p/labelling-ai-generated-content",
            "https://www.clickhouse.com/blog/release",
            "https://www.eu-startups.com/2026/09/germanys-sprind-and-the-netherlands-nadi-launch",
        ],
    )
    def test_story_pages_are_not_wrappers(self, url):
        assert not is_link_wrapper(url)
        assert is_story_url(url)

    @pytest.mark.parametrize(
        "url", ["https://img.youtube.com/vi/fQdkNGZqYZA/0.jpg", "https://finance.yahoo.com/?err=404"]
    )
    def test_images_and_error_pages_are_no_story(self, url):
        assert not is_story_url(url)


class TestStripTracking:
    def test_drops_tracking_keeps_the_rest(self):
        url = "https://sifted.eu/a?utm_campaign=Daily&utm_medium=email&_hsmi=42&page=2#top"

        assert strip_tracking(url) == "https://sifted.eu/a?page=2#top"

    def test_url_without_query_is_unchanged(self):
        assert strip_tracking("https://example.com/a/") == "https://example.com/a/"

    @pytest.mark.parametrize(
        "url",
        [
            "https://eur-lex.europa.eu/legal-content/ES/ALL/?uri=CELEX:32024R2847",
            "https://www.sciencedirect.com/science/article/pii/S1383762125002048?via%3Dihub",
        ],
    )
    def test_url_without_tracking_keeps_every_byte(self, url):
        """Regression: re-encoding the query turned ``?via%3Dihub`` into ``?via%3Dihub=``."""
        assert strip_tracking(url) == url


class TestUnwrapQueryRedirect:
    def test_google_redirect_carries_its_destination(self):
        url = "https://www.google.com/url?q=https%3A%2F%2Fwww.eu-startups.com%2F2026%2F08%2Fvolta%2F&amp%3Bsa=D"

        assert unwrap_query_redirect(url) == "https://www.eu-startups.com/2026/08/volta/"

    def test_other_urls_carry_none(self):
        assert unwrap_query_redirect("https://example.com/url?q=https://x.com") is None
