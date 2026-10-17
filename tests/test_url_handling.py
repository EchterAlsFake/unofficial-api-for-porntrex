"""Offline regressions for URL identity, pagination and listing contracts."""

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from urllib.parse import parse_qs, urlsplit

from porntrex_api import api as api


class EmptyStream:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    def __aiter__(self):
        return self

    async def __anext__(self):
        raise StopAsyncIteration


class UrlHandlingTests(unittest.IsolatedAsyncioTestCase):
    async def test_filtered_profile_fetches_two_distinct_pages(self):
        media = api.Model(url="https://www.porntrex.com/models/Example/?sort_by=views&from=09#videos", core=object())
        capture = Mock(return_value=EmptyStream())
        from contextlib import ExitStack

        with ExitStack() as stack:
            for name in ("scrape_stream", "_scrape_stream"):
                if hasattr(api, name):
                    stack.enter_context(patch.object(api, name, capture))
            if hasattr(api, "Helper"):
                stack.enter_context(patch.object(api, "Helper", lambda **kwargs: SimpleNamespace(iterator=capture)))
            stack.enter_context(patch.object(api.Model, "get_field", AsyncMock(return_value=2)))
            async for _ in media.videos(pages=2):
                pass
        urls = capture.call_args.kwargs["target_page_urls"]
        self.assertEqual([parse_qs(urlsplit(url).query)["from"] for url in urls], [["01"], ["02"]])
        self.assertTrue(all(parse_qs(urlsplit(url).query)["sort_by"] == ["views"] for url in urls))
        self.assertTrue(all(not urlsplit(url).fragment for url in urls))


if __name__ == "__main__":
    unittest.main()
