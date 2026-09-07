"""Límites de workers, orden de resultados y cancelación de lecturas."""

import asyncio

import pytest

from app.shared.concurrency import map_limited


async def test_map_limited_bounds_workers_and_keeps_order():
    active = peak = 0

    async def read(value):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        try:
            await asyncio.sleep(0)
            if value == 5:
                raise ValueError("lectura fallida")
            return value * 2
        finally:
            active -= 1

    results = await map_limited(list(range(100)), read, limit=4)
    assert peak == 4
    assert isinstance(results[5], ValueError)
    assert [result for index, result in enumerate(results) if index != 5] == [i * 2 for i in range(100) if i != 5]
    assert active == 0


async def test_cancellation_stops_all_workers():
    started = asyncio.Event()
    active = 0

    async def read(_value):
        nonlocal active
        active += 1
        if active == 3:
            started.set()
        try:
            await asyncio.Event().wait()
        finally:
            active -= 1

    task = asyncio.create_task(map_limited(list(range(100)), read, limit=3))
    await asyncio.wait_for(started.wait(), timeout=1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert active == 0


async def test_empty_input_and_invalid_limit():
    async def read(value):
        return value

    assert await map_limited([], read, limit=4) == []
    with pytest.raises(ValueError):
        await map_limited([1], read, limit=0)
