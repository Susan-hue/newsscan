import httpx
import pytest

from newsscan.analysis.factcheck import (
    FactCheck,
    FactCheckError,
    FakeFactCheckLookup,
    GoogleFactCheckLookup,
    parse_fact_checks,
)

GOOD = {
    "claims": [
        {
            "text": "Unemployment fell to 3.1 percent",
            "claimReview": [
                {
                    "publisher": {"name": "Example Checker", "site": "example.org"},
                    "url": "https://example.org/check/1",
                    "title": "Did unemployment fall?",
                    "textualRating": "Mostly true",
                    "reviewDate": "2025-01-02T00:00:00Z",
                }
            ],
        }
    ]
}


def _lookup(handler):
    return GoogleFactCheckLookup("test-key", client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_parse_good_response():
    [item] = parse_fact_checks(GOOD, 3)
    assert item.publisher == "Example Checker" and item.rating == "Mostly true"
    assert item.url == "https://example.org/check/1"


def test_parse_drops_unsafe_or_incomplete_results():
    bad = {
        "claims": [
            "not a dict",
            {"claimReview": "nope"},
            {"text": "x", "claimReview": [{"url": "javascript:alert(1)", "textualRating": "False"}]},
            {"text": "x", "claimReview": [{"url": "data:text/html,hi", "textualRating": "False"}]},
            {"text": "x", "claimReview": [{"url": "https://ok.example/a", "textualRating": ""}]},
            {"text": "x", "claimReview": [{"url": "https://ok.example/a", "textualRating": "False"}]},
        ]
    }
    items = parse_fact_checks(bad, 5)
    assert [i.url for i in items] == ["https://ok.example/a"]
    assert parse_fact_checks("junk", 3) == [] and parse_fact_checks({}, 3) == []


def test_parse_respects_limit_and_truncates():
    many = {"claims": [GOOD["claims"][0]] * 5}
    assert len(parse_fact_checks(many, 2)) == 2
    long = {
        "claims": [
            {"text": "t" * 1000, "claimReview": [{"url": "https://a.b/c", "textualRating": "r" * 1000}]}
        ]
    }
    assert len(parse_fact_checks(long, 1)[0].rating) == 300


def test_key_is_sent_in_a_header_not_the_url():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["key"] = request.headers["x-goog-api-key"]
        return httpx.Response(200, json=GOOD)

    assert len(_lookup(handler).search("Unemployment fell", 3)) == 1
    assert seen["key"] == "test-key" and "test-key" not in seen["url"]
    assert "query=Unemployment" in seen["url"]


@pytest.mark.parametrize(
    "response",
    [httpx.Response(403, text="secret detail"), httpx.Response(429), httpx.Response(200, text="not json")],
)
def test_failures_become_safe_errors(response):
    with pytest.raises(FactCheckError) as info:
        _lookup(lambda request: response).search("claim")
    assert "secret detail" not in str(info.value) and "test-key" not in str(info.value)


def test_network_error_becomes_safe_error():
    def handler(request):
        raise httpx.ConnectError("boom test-key")

    with pytest.raises(FactCheckError) as info:
        _lookup(handler).search("claim")
    assert "test-key" not in str(info.value)


def test_no_matches_is_an_empty_list_not_an_error():
    assert _lookup(lambda request: httpx.Response(200, json={})).search("obscure claim") == []


def test_fake_lookup():
    item = FactCheck("c", "p", "https://a.b", "t", "False", "d")
    assert FakeFactCheckLookup({"c": [item]}).search("c") == [item]
    assert FakeFactCheckLookup().search("other") == []
