import pytest
from unittest.mock import MagicMock
from services.youtube_client import _with_retry, _with_retry_async

def test_with_retry_sync_success():
    func = MagicMock(return_value="success")
    result = _with_retry(func)
    assert result == "success"
    func.assert_called_once()

@pytest.mark.asyncio
async def test_with_retry_async_success():
    func = MagicMock(return_value="success_async")
    result = await _with_retry_async(func)
    assert result == "success_async"
    func.assert_called_once()
