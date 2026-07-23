from unittest.mock import AsyncMock

import pytest

from src.core import utils


@pytest.mark.asyncio
async def test_apply_jitter_sleeps_for_a_value_within_range(monkeypatch):
    sleep_mock = AsyncMock()
    monkeypatch.setattr(utils.asyncio, "sleep", sleep_mock)
    monkeypatch.setattr(utils.random, "uniform", lambda lo, hi: 1.5)

    await utils.apply_jitter(min_seconds=1.0, max_seconds=2.0)

    sleep_mock.assert_awaited_once_with(1.5)


@pytest.mark.asyncio
async def test_move_mouse_naturally_moves_through_every_waypoint(monkeypatch):
    monkeypatch.setattr(utils.asyncio, "sleep", AsyncMock())
    page = AsyncMock()

    await utils._move_mouse_naturally(page, waypoints=3)

    assert page.mouse.move.await_count == 3


@pytest.mark.asyncio
async def test_scroll_naturally_scrolls_down_and_sometimes_back(monkeypatch):
    monkeypatch.setattr(utils.asyncio, "sleep", AsyncMock())
    monkeypatch.setattr(utils.random, "randint", lambda lo, hi: lo)
    monkeypatch.setattr(utils.random, "random", lambda: 0.0)  # forces the back-scroll branch
    page = AsyncMock()

    await utils._scroll_naturally(page)

    # randint(2, 4) is stubbed to always return 2 -> 2 forward scrolls + 1 back-scroll.
    assert page.evaluate.await_count == 3


@pytest.mark.asyncio
async def test_scroll_naturally_skips_back_scroll_when_unlucky(monkeypatch):
    monkeypatch.setattr(utils.asyncio, "sleep", AsyncMock())
    monkeypatch.setattr(utils.random, "randint", lambda lo, hi: lo)
    monkeypatch.setattr(utils.random, "random", lambda: 0.99)  # skips the back-scroll branch
    page = AsyncMock()

    await utils._scroll_naturally(page)

    assert page.evaluate.await_count == 2


@pytest.mark.asyncio
async def test_hover_random_element_hovers_when_lucky(monkeypatch):
    monkeypatch.setattr(utils.asyncio, "sleep", AsyncMock())
    monkeypatch.setattr(utils.random, "random", lambda: 0.0)  # < 0.6 triggers the hover
    monkeypatch.setattr(utils.random, "randint", lambda lo, hi: lo)
    page = AsyncMock()
    handle = AsyncMock()
    handle.bounding_box.return_value = {"x": 10.0, "y": 20.0, "width": 100.0, "height": 40.0}
    page.query_selector.return_value = handle

    await utils._hover_random_element(page)

    page.mouse.move.assert_awaited_once_with(60.0, 40.0, steps=8)


@pytest.mark.asyncio
async def test_hover_random_element_skips_when_unlucky(monkeypatch):
    monkeypatch.setattr(utils.random, "random", lambda: 0.99)  # >= 0.6 skips the hover
    page = AsyncMock()

    await utils._hover_random_element(page)

    page.query_selector.assert_not_called()


@pytest.mark.asyncio
async def test_hover_random_element_handles_no_matching_element(monkeypatch):
    monkeypatch.setattr(utils.random, "random", lambda: 0.0)
    page = AsyncMock()
    page.query_selector.return_value = None

    await utils._hover_random_element(page)

    page.mouse.move.assert_not_called()


@pytest.mark.asyncio
async def test_hover_random_element_handles_no_bounding_box(monkeypatch):
    monkeypatch.setattr(utils.random, "random", lambda: 0.0)
    page = AsyncMock()
    handle = AsyncMock()
    handle.bounding_box.return_value = None
    page.query_selector.return_value = handle

    await utils._hover_random_element(page)

    page.mouse.move.assert_not_called()


@pytest.mark.asyncio
async def test_hover_random_element_swallows_exceptions(monkeypatch):
    monkeypatch.setattr(utils.random, "random", lambda: 0.0)
    page = AsyncMock()
    page.query_selector.side_effect = RuntimeError("boom")

    await utils._hover_random_element(page)  # must not raise


@pytest.mark.asyncio
async def test_simulate_human_interaction_returns_true_on_first_clean_title(monkeypatch):
    monkeypatch.setattr(utils.asyncio, "sleep", AsyncMock())
    monkeypatch.setattr(utils, "_move_mouse_naturally", AsyncMock())
    monkeypatch.setattr(utils, "_scroll_naturally", AsyncMock())
    monkeypatch.setattr(utils, "_hover_random_element", AsyncMock())
    page = AsyncMock()
    page.query_selector.return_value = None  # no cloudflare iframe
    page.title.return_value = "Real Product Title"

    result = await utils.simulate_human_interaction(page)

    assert result is True
    page.title.assert_awaited_once()


@pytest.mark.asyncio
async def test_simulate_human_interaction_returns_false_after_max_attempts(monkeypatch):
    monkeypatch.setattr(utils.asyncio, "sleep", AsyncMock())
    monkeypatch.setattr(utils, "_move_mouse_naturally", AsyncMock())
    monkeypatch.setattr(utils, "_scroll_naturally", AsyncMock())
    monkeypatch.setattr(utils, "_hover_random_element", AsyncMock())
    page = AsyncMock()
    page.query_selector.return_value = None
    page.title.return_value = "Just a moment..."

    result = await utils.simulate_human_interaction(page, max_attempts=2)

    assert result is False
    assert page.title.await_count == 2


@pytest.mark.asyncio
async def test_simulate_human_interaction_clicks_cloudflare_iframe_when_present(monkeypatch):
    monkeypatch.setattr(utils.asyncio, "sleep", AsyncMock())
    monkeypatch.setattr(utils, "_move_mouse_naturally", AsyncMock())
    monkeypatch.setattr(utils, "_scroll_naturally", AsyncMock())
    monkeypatch.setattr(utils, "_hover_random_element", AsyncMock())
    page = AsyncMock()
    iframe = AsyncMock()
    iframe.bounding_box.return_value = {"x": 0.0, "y": 0.0, "width": 300.0, "height": 65.0}
    page.query_selector.return_value = iframe
    page.title.return_value = "Real Product Title"

    result = await utils.simulate_human_interaction(page)

    assert result is True
    page.mouse.click.assert_awaited_once_with(150.0, 32.5)


@pytest.mark.asyncio
async def test_simulate_human_interaction_swallows_cloudflare_iframe_errors(monkeypatch):
    monkeypatch.setattr(utils.asyncio, "sleep", AsyncMock())
    monkeypatch.setattr(utils, "_move_mouse_naturally", AsyncMock())
    monkeypatch.setattr(utils, "_scroll_naturally", AsyncMock())
    monkeypatch.setattr(utils, "_hover_random_element", AsyncMock())
    page = AsyncMock()
    page.query_selector.side_effect = RuntimeError("boom")
    page.title.return_value = "Real Product Title"

    result = await utils.simulate_human_interaction(page)  # must not raise

    assert result is True


def test_uuid7_generation():
    import time
    u1 = utils.uuid7()
    time.sleep(0.002)
    u2 = utils.uuid7()

    assert u1.version == 7
    assert u2.version == 7
    assert u1 != u2
    assert u1 <= u2


