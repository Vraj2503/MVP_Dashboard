import asyncio
from sqlalchemy import text
from app.db import AppSessionLocal

async def main():
    async with AppSessionLocal() as session:
        sql1 = "SELECT s.name FROM students s JOIN student_summary ss ON s.id = ss.student_id WHERE ss.attendance_rate < 0.7 AND ss.grade_avg > 80"
        res1 = await session.execute(text(sql1))
        print("SQL1 Results:", res1.fetchall())

        sql2 = "SELECT s.name FROM students s JOIN student_summary ss ON s.id = ss.student_id WHERE ss.attendance_rate < 0.5 AND ss.grade_avg > 80"
        res2 = await session.execute(text(sql2))
        print("SQL2 Results:", res2.fetchall())
            
asyncio.run(main())
