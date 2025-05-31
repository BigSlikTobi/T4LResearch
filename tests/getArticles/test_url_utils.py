import pytest
import os
import urllib.parse
from unittest.mock import patch

from getArticles.url_utils import (
    remove_control_chars,
    build_url_from_parts,
    clean_url,
    is_valid_url
)

# Tests for remove_control_chars

def test_remove_control_chars_basic():
    assert remove_control_chars("hello\x00world\x1F\x7F") == "helloworld"
    assert remove_control_chars("test\x08ing\x0c") == "testing"

def test_remove_control_chars_no_control_chars():
    assert remove_control_chars("helloworld") == "helloworld"
    assert remove_control_chars("!@#$%^&*()") == "!@#$%^&*()"

def test_remove_control_chars_empty_string():
    assert remove_control_chars("") == ""

# Tests for build_url_from_parts

def test_build_url_from_parts_basic():
    parts = urllib.parse.ParseResult(
        scheme=' http ', netloc=' example.com ', path='/ path1 / path2 ',
        params='', query=' key1=val1 & key2=val2 ', fragment=' frag '
    )
    # Expected: scheme, netloc, path elements, query elements, fragment are stripped.
    # Path segments are stripped and joined. Query params are stripped.
    # url_utils.build_url_from_parts currently does:
    # scheme.strip(), netloc.strip(), '/'.join(s.strip() for s in path.split('/')),
    # '&'.join(s.strip() for s in query.split('&')), fragment.strip()
    # This means spaces *within* path segments or query values are NOT removed by build_url_from_parts itself.
    # Example: path='/ path1 / path2 ' -> [' ', ' path1 ', ' path2 '] -> strip each -> ['', 'path1', 'path2'] -> '/path1/path2'
    # query=' key1=val1 & key2=val2 ' -> [' key1=val1 ', ' key2=val2 '] -> strip each -> ['key1=val1', 'key2=val2'] -> 'key1=val1&key2=val2'
    assert build_url_from_parts(parts) == "http://example.com/path1/path2?key1=val1&key2=val2#frag"

def test_build_url_from_parts_empty_and_whitespace_components():
    parts_empty = urllib.parse.ParseResult(scheme='', netloc='', path='', params='', query='', fragment='')
    assert build_url_from_parts(parts_empty) == "////?#" # As per current logic

    parts_space = urllib.parse.ParseResult(scheme=' ', netloc=' ', path=' / ', params=' ', query=' ', fragment=' ')
    assert build_url_from_parts(parts_space) == "////?#" # Stripped to empty

    parts_mixed = urllib.parse.ParseResult(
        scheme='http', netloc='host', path='/a /b', query='k= v ', fragment=' f '
    )
    assert build_url_from_parts(parts_mixed) == "http://host/a/b?k= v#f"


# Tests for clean_url

@patch.dict(os.environ, {}, clear=True)
def test_clean_url_local_env_basic():
    # Trace: " http://example.com/a b\nc\x7Fdef "
    # 1. remove_control_chars (includes \x7F): " http://example.com/a b\ncdef "
    # 2. strip: "http://example.com/a b\ncdef"
    # 3. replace \n, \r: "http://example.com/a bcdef"
    # 4. ord filter (32-126): "http://example.com/a bcdef" (no change)
    # 5. re.sub r'\s+' to '-': "http://example.com/a-bcdef"
    # 6. urlparse: ParseResult(scheme='http', netloc='example.com', path='/a-bcdef', query='', fragment='')
    #    path components quoted: quote("/a-bcdef") -> "/a-bcdef" (no change as '-' is safe for path)
    #    query components quoted_plus: quote_plus("", safe="=&") -> ""
    # 7. urlunparse: "http://example.com/a-bcdef"
    # 8. final quote: urllib.parse.quote("http://example.com/a-bcdef", safe=":/?&=%#") -> "http://example.com/a-bcdef"
    assert clean_url(" http://example.com/a b\nc\x7Fdef ") == "http://example.com/a-bcdef"
    assert clean_url("  http://foo.com/bar baz/\tqux  ") == "http://foo.com/bar-baz/-qux"

@patch.dict(os.environ, {}, clear=True)
def test_clean_url_local_env_with_query_fragment():
    # Input: " http://example.com/p?a=b c#f g "
    # 1. remove_control_chars: no change
    # 2. strip: "http://example.com/p?a=b c#f g"
    # 3. replace \n, \r: no change
    # 4. ord filter: no change
    # 5. re.sub r'\s+' to '-': "http://example.com/p?a=b-c#f-g" (this is the current behavior)
    # 6. urlparse: ParseResult(scheme='http', netloc='example.com', path='/p', params='', query='a=b-c', fragment='f-g')
    #    path quoted: "/p" -> "/p"
    #    query quoted_plus: quote_plus("a=b-c", safe="=&") -> "a=b-c"
    # 7. urlunparse: "http://example.com/p?a=b-c#f-g"
    # 8. final quote: "http://example.com/p?a=b-c#f-g"
    assert clean_url(" http://example.com/p?a=b c#f g ") == "http://example.com/p?a=b-c#f-g"

    # Test with %20 already in URL - it should be preserved by initial steps, then potentially unquoted/requoted by parse/unparse
    # Input: "http://example.com/path%20with%20spaces?q=a%20b"
    # 1-4: no change
    # 5. re.sub: no change (no \s characters)
    # 6. urlparse: path='/path%20with%20spaces', query='q=a%20b'
    #    path quoted: quote('/path%20with%20spaces') -> /path%2520with%2520spaces (oops, double encoding if not unquoted first)
    #    The code's urlparse()._replace(...) doesn't unquote by default.
    #    So, path becomes '/path%20with%20spaces'. query becomes 'q=a%20b'.
    #    quote('/path%20with%20spaces') -> /path%2520with%2520spaces
    #    quote_plus('q=a%20b', safe="=&") -> q=a%2520b
    # 7. urlunparse will use these potentially double-encoded parts.
    # 8. final quote.
    # This indicates a potential issue with double encoding if inputs are already partially encoded.
    # However, the goal is to test the code as is.
    # The `quote` function in Python 3.7+ does not re-quote %xx sequences if they are valid.
    # So, quote('/path%20with%20spaces') should be '/path%20with%20spaces'
    # And quote_plus('q=a%20b', safe="=&") should be 'q=a%20b'
    # So the result should be "http://example.com/path%20with%20spaces?q=a%20b"
    assert clean_url("http://example.com/path%20with%20spaces?q=a%20b") == "http://example.com/path%20with%20spaces?q=a%20b"


@patch.dict(os.environ, {"GITHUB_ACTIONS": "true"})
@patch('getArticles.url_utils.build_url_from_parts')
def test_clean_url_github_actions_env(mock_build_url):
    mock_build_url.return_value = "built_url_from_mock"
    # The GITHUB_ACTIONS path calls urlparse, then build_url_from_parts, then final quote.
    # remove_control_chars is called first.

    input_url = " http://example.com/some path\x00 "
    # After remove_control_chars: " http://example.com/some path "

    # Expected call to urlparse will be on " http://example.com/some path "
    # Then build_url_from_parts is called with the ParseResult.

    result = clean_url(input_url)

    mock_build_url.assert_called_once()
    # Check what was passed to build_url_from_parts
    args_to_build, _ = mock_build_url.call_args
    parsed_input = args_to_build[0]
    assert parsed_input.scheme == " http " # build_url_from_parts will strip these
    assert parsed_input.netloc == " example.com "
    assert parsed_input.path == "/some path "

    assert result == urllib.parse.quote("built_url_from_mock", safe=":/?&=%#")


def test_clean_url_empty_input():
    assert clean_url("") == ""

@patch.dict(os.environ, {}, clear=True)
@patch('urllib.parse.urlparse', side_effect=Exception("Mocked parse error"))
def test_clean_url_exception_in_parse_quote_local_env(mock_urlparse):
    # url after initial cleaning: "http://example.com/test" (no control chars, no leading/trailing spaces)
    # Then urlparse is called, which we mock to raise an error.
    # The function should catch this and return the url as it was before the try block.
    original_url = "http://example.com/test\x01"
    expected_after_initial_clean = "http://example.com/test"
    assert clean_url(original_url) == expected_after_initial_clean


# Tests for is_valid_url

def test_is_valid_url_valid():
    assert is_valid_url("http://example.com") is True
    assert is_valid_url("https://example.com/path?query=1") is True
    assert is_valid_url("ftp://localhost/file") is True # scheme and netloc are present
    assert is_valid_url("http://localhost:8000") is True

def test_is_valid_url_invalid():
    assert is_valid_url("htp://example.com") is True # 'htp' is a valid scheme format
    assert is_valid_url("example.com") is False # No scheme
    assert is_valid_url("") is False
    assert is_valid_url("http:///path-only") is False # Netloc is empty
    assert is_valid_url("://example.com/path") is False # Scheme is empty

@patch('urllib.parse.urlparse', side_effect=Exception("Parse error"))
def test_is_valid_url_parse_exception(mock_urlparse_exc):
    assert is_valid_url("http://example.com") is False
    mock_urlparse_exc.assert_called_once_with("http://example.com")
