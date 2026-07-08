import asyncio
from app.db import engine
from app.services.nl2sql import load_schema_ddl, get_system_prompt

async def test():
    await load_schema_ddl(engine)
    prompt = get_system_prompt()
    print("PROMPT PREVIEW:")
    print(prompt[:500])
    print("...")
    print(prompt[1500:2000])

asyncio.run(test())
