import asyncio
from sqlalchemy import text
from app.db import AppSessionLocal

async def main():
    async with AppSessionLocal() as session:
        print("=== TABLES IN DATABASE ===")
        res = await session.execute(text("SHOW TABLES"))
        tables = [r[0] for r in res.fetchall()]
        for t in tables:
            print(f"- {t}")
        
        print("\n=== SCHEMA FOR student_summary ===")
        res = await session.execute(text("DESCRIBE student_summary"))
        for r in res.fetchall():
            print(f"{r[0]:<20} {r[1]:<15} {r[2]:<5} {r[3]:<5} {r[4]}")
            
        print("\n=== SAMPLE DATA FROM student_summary (Limit 5) ===")
        res = await session.execute(text("SELECT * FROM student_summary LIMIT 5"))
        cols = res.keys()
        print(" | ".join(cols))
        print("-" * 80)
        for r in res.fetchall():
            print(" | ".join(str(x) for x in r))

asyncio.run(main())
