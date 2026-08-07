from .. import Client, Video
from base_api.base import BaseCore
import pytest

@pytest.mark.asyncio
async def test_all():

    core = BaseCore()
    core.configuration.videos_concurrency = 1
    core.configuration.pages_concurrency = 1

    client = Client(core)
    model = await client.get_model("https://www.porntrex.com/channels/nubile-films/")

    assert isinstance(model.name, str) and len(model.name) > 0
    assert isinstance(model.information, dict) and len(model.information) > 0

    idx = 0
    async for video in model.videos():
        idx += 1
        assert isinstance(video.unwrap().title, str)

        if idx >= 5:
            break

