import asyncio
from sqlalchemy import text
from app.db import engine

async def drop_all():
    async with engine.begin() as c:
        await c.execute(text('SET FOREIGN_KEY_CHECKS = 0;'))
        tables = ['attendance', 'grades', 'assignments', 'assessments', 'classes', 'fees', 'behavior_notes', 'student_summary', 'chat_logs', 'alerts', 'digests', 'students', 'departments', 'teachers', 'enrollments']
        for t in tables:
            await c.execute(text(f'DROP TABLE IF EXISTS {t};'))
        await c.execute(text('SET FOREIGN_KEY_CHECKS = 1;'))
    print("Tables dropped.")

if __name__ == '__main__':
    asyncio.run(drop_all())
