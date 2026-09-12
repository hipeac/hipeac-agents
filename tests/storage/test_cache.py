"""Unit tests for the generic JSON file cache."""

from hipeac_agents.storage import cache as json_cache


def test_cache_key_is_stable_and_namespaced():
    assert json_cache.cache_key("scrape", "https://example.com/a") == json_cache.cache_key(
        "scrape", "https://example.com/a"
    )
    assert json_cache.cache_key("scrape", "https://example.com/a") != json_cache.cache_key(
        "search", "https://example.com/a"
    )
    assert json_cache.cache_key("scrape", "https://example.com/a").startswith("scrape-")


def test_round_trip(tmp_path):
    path = json_cache.cache_dir(tmp_path, "scrape") / f"{json_cache.cache_key('scrape', 'u1')}.json"

    assert json_cache.cache_get(path) is None
    json_cache.cache_put(path, {"url": "u1", "markdown": "m"})
    assert json_cache.cache_get(path)["payload"] == {"markdown": "m", "url": "u1"}
    assert "cached_at" in json_cache.cache_get(path)


def test_get_corrupt_file_returns_none(tmp_path):
    path = json_cache.cache_dir(tmp_path, "scrape") / "broken.json"
    path.parent.mkdir(parents=True)
    path.write_text("{not json", encoding="utf-8")

    assert json_cache.cache_get(path) is None
