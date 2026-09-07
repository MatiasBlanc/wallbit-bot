"""Concurrencia por usuario con conversaciones serializadas y registro de locks acotado."""

import asyncio
from datetime import datetime, timezone

import pytest
from telegram import Chat, Message, Update, User

from app.bot.processor import PerUserUpdateProcessor


def update_for(user_id, update_id=1):
    return Update(update_id, message=Message(update_id, datetime.now(timezone.utc),
                  Chat(user_id, "private"), from_user=User(user_id, "Usuario", False)))


async def test_users_run_in_parallel_but_each_conversation_is_serial():
    processor = PerUserUpdateProcessor(4)
    active = set()
    peak = 0
    completed = []

    async def work(user_id, number):
        nonlocal peak
        assert user_id not in active
        active.add(user_id)
        peak = max(peak, len(active))
        await asyncio.sleep(0.01)
        active.remove(user_id)
        completed.append((user_id, number))

    async with processor:
        await asyncio.gather(*[
            processor.process_update(update_for(user_id, number), work(user_id, number))
            for user_id, number in [(101, 1), (101, 2), (202, 1), (202, 2)]
        ])
        assert processor._queues == {}
    assert peak == 2
    assert completed.index((101, 1)) < completed.index((101, 2))
    assert completed.index((202, 1)) < completed.index((202, 2))


async def test_processor_releases_lock_on_error():
    processor = PerUserUpdateProcessor(2)
    async def fail():
        raise RuntimeError("test")
    with pytest.raises(RuntimeError):
        await processor.process_update(update_for(101), fail())
    assert processor._queues == {}


async def test_cancellation_of_waiter_releases_registration():
    processor = PerUserUpdateProcessor(2)
    started = asyncio.Event()
    release = asyncio.Event()
    async def first():
        started.set()
        await release.wait()
    async def second():
        pytest.fail("Una tarea cancelada mientras espera no debe ejecutarse")
    task = asyncio.create_task(processor.process_update(update_for(101), first()))
    await started.wait()
    waiter = asyncio.create_task(processor.process_update(update_for(101), second()))
    await asyncio.sleep(0)
    waiter.cancel()
    with pytest.raises(asyncio.CancelledError):
        await waiter
    release.set()
    await task
    assert processor._queues == {}
