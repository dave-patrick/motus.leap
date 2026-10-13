from unittest.mock import MagicMock, patch
import sys
import types
import core.actions as actions


def fake_playwright(runtime):
    module = types.ModuleType('playwright.sync_api')
    module.sync_playwright = MagicMock(return_value=MagicMock(start=MagicMock(return_value=runtime)))
    return module


def test_failed_launch_stops_runtime_before_retry():
    runtime = MagicMock()
    runtime.chromium.launch_persistent_context.side_effect = RuntimeError('missing browser')
    with patch.dict(sys.modules, {'playwright.sync_api': fake_playwright(runtime)}):
        assert actions.get_playwright_browser() is None
        assert actions.get_playwright_browser() is None
    assert runtime.stop.call_count == 2


def test_failure_after_launch_closes_context_and_runtime():
    runtime = MagicMock()
    context = runtime.chromium.launch_persistent_context.return_value
    context.pages = []
    context.new_page.side_effect = RuntimeError('page initialization failed')
    with patch.dict(sys.modules, {'playwright.sync_api': fake_playwright(runtime)}), patch('os.path.exists', return_value=False):
        assert actions.get_playwright_browser() is None
    context.close.assert_called_once()
    runtime.stop.assert_called_once()
