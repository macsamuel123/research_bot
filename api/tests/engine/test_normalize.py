from __future__ import annotations

from urllib.parse import parse_qsl, urlsplit

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.engine.normalize import InvalidUrl, normalize_text, normalize_url

pytestmark = pytest.mark.criterion("M8-C6")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (
            "HTTPS://WWW.Example.COM/a?utm_source=x&b=2&a=1#top",
            "https://www.example.com/a?a=1&b=2",
        ),
        ("https://e.com/p?utm_medium=m&x=1", "https://e.com/p?x=1"),
        ("https://e.com/p?UTM_Medium=m&x=1", "https://e.com/p?x=1"),
        ("https://e.com/p?utm_campaign=c&utm_term=t&utm_content=z", "https://e.com/p"),
        ("https://e.com/p?fbclid=abc&x=1", "https://e.com/p?x=1"),
        ("https://e.com/p?gclid=abc&x=1", "https://e.com/p?x=1"),
        ("https://e.com/p?mc_cid=1&mc_eid=2&x=1", "https://e.com/p?x=1"),
        ("https://e.com/p?ref=hn&x=1", "https://e.com/p?x=1"),
        ("https://e.com/p?referrer=keep", "https://e.com/p?referrer=keep"),
        ("https://e.com/p#section-2", "https://e.com/p"),
        ("https://e.com/p?z=1&a=2&m=3", "https://e.com/p?a=2&m=3&z=1"),
        ("https://e.com/p?a=2&a=1", "https://e.com/p?a=1&a=2"),
        ("https://e.com/p?q=a+b", "https://e.com/p?q=a+b"),
        ("https://e.com/p?q=a%20b", "https://e.com/p?q=a+b"),
        ("https://e.com/p?q=a%2Bb", "https://e.com/p?q=a%2Bb"),
        ("https://e.com", "https://e.com/"),
        ("https://e.com?b=1", "https://e.com/?b=1"),
        ("http://Example.com:8080/Path", "http://example.com:8080/Path"),
        ("  https://e.com/x  ", "https://e.com/x"),
        ("https://e.com/p?flag", "https://e.com/p?flag="),
    ],
)
def test_normalize_table(raw: str, expected: str) -> None:
    assert normalize_url(raw) == expected
    assert normalize_url(expected) == expected


@pytest.mark.parametrize("raw", ["http://a.com:99999/", "http://[::1", "http://a.com:port/"])
def test_invalid_url_raises_invalidurl(raw: str) -> None:
    with pytest.raises(InvalidUrl):
        normalize_url(raw)
    assert issubclass(InvalidUrl, ValueError)


TRACKING_KEYS = ["utm_source", "UTM_Medium", "fbclid", "gclid", "mc_cid", "mc_eid", "ref"]
_label = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-",
    min_size=1,
    max_size=10,
)
_segment = st.lists(
    st.one_of(st.text(alphabet="abcXYZ019._~-", min_size=1, max_size=6), st.just("%20")),
    min_size=1,
    max_size=3,
).map("".join)
_key = st.one_of(
    st.text(alphabet="abcdefxyz_", min_size=1, max_size=6), st.sampled_from(TRACKING_KEYS)
)
_value = st.one_of(
    st.text(alphabet="abc 123+", max_size=6), st.sampled_from(["%20", "a+b", "x y", "a%20b"])
)


@st.composite
def urls(draw: st.DrawFn) -> str:
    scheme = draw(st.sampled_from(["http", "https", "HTTP", "HTTPS"]))
    host = ".".join(draw(st.lists(_label, min_size=1, max_size=3)))
    port = draw(st.one_of(st.none(), st.integers(1, 65535)))
    path = "".join("/" + s for s in draw(st.lists(_segment, max_size=3)))
    pairs = draw(st.lists(st.tuples(_key, _value), max_size=5))
    query = "&".join(f"{k}={v}" for k, v in pairs)
    frag = draw(st.one_of(st.none(), st.text(alphabet="abc12", max_size=5)))
    url = f"{scheme}://{host}" + (f":{port}" if port else "") + path
    if query:
        url += "?" + query
    if frag is not None:
        url += "#" + frag
    return url


@given(urls())
def test_normalize_idempotent(url: str) -> None:
    once = normalize_url(url)
    assert normalize_url(once) == once
    parts = urlsplit(once)
    assert parts.fragment == "" and "#" not in once
    assert parts.scheme in ("http", "https")
    keys = [k.lower() for k, _ in parse_qsl(parts.query, keep_blank_values=True)]
    assert not any(
        k.startswith("utm_") or k in {"fbclid", "gclid", "mc_cid", "mc_eid", "ref"} for k in keys
    )


def test_normalize_text() -> None:
    assert normalize_text("  Ｈello\t\nWORLD  ") == "hello world"
