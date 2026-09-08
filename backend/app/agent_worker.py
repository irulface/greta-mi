"""Dedicated worker keeps agent network reads independent from indexing and SMTP."""
import asyncio
import logging
from .autonomous import agent_tick


async def worker():
    while True:
        try: await agent_tick()
        except Exception: logging.getLogger(__name__).exception('Autonomous agent cycle failed')
        await asyncio.sleep(5)


if __name__ == '__main__': asyncio.run(worker())
