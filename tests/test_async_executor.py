import asyncio

from src.core.concurrency.async_executor import AsyncExecutor


def test_async_executor_initializes_semaphore_before_task_execution():
    async def run_task():
        executor = AsyncExecutor(max_concurrent=2)

        async def task():
            return "done"

        submitted = await executor.submit_async(task())
        try:
            return await submitted
        finally:
            await executor.shutdown()

    assert asyncio.run(run_task()) == "done"
