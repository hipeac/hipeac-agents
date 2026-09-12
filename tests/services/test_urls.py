"""Unit tests for URL display/canonicalization helpers (no mocking)."""

from hipeac_agents.services.urls import display_domain


class TestDisplayDomain:
    def test_strips_www(self):
        assert display_domain("https://www.example.com/a/b?q=1") == "example.com"

    def test_keeps_bare_domain(self):
        assert display_domain("https://example.com/a") == "example.com"

    def test_keeps_subdomain_other_than_www(self):
        assert display_domain("https://blog.example.com/a") == "blog.example.com"

    def test_empty_url_returns_itself(self):
        assert display_domain("") == ""
