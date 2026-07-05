import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()

async def check_fees():
    url = os.getenv("APP_DATABASE_URL")
    engine = create_async_engine(url)
    
    query = """
    SELECT status, MIN(due_date) as min_date, MAX(due_date) as max_date, COUNT(*) as count 
    FROM fees 
    GROUP BY status
    """
    
    async with engine.begin() as conn:
        result = await conn.execute(text(query))
        rows = result.fetchall()
        print("Fee Status Breakdown and Ranges:")
        for row in rows:
            print(f"- Status: {row[0]}")
            print(f"  Range: {row[1]} to {row[2]}")
            print(f"  Count: {row[3]}\n")

asyncio.run(check_fees())
