from .. import Client
from base_api import BaseCore
import pytest

@pytest.mark.asyncio
async def test_all():
    core = BaseCore()
    core.configuration.pages_concurrency = 1
    core.configuration.videos_concurrency = 1

    client = Client(core=core)
    search = client.search(query="stepmom")

    idx = 0
    async for video in search:

        idx += 1
        assert isinstance(video.video.title, str)
        if idx == 5:
            break
