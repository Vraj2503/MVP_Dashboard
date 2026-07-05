import asyncio
from sqlalchemy import select
from app.db import AppSessionLocal
from app.models import ChatLog, StudentSummary, Student

async def main():
    async with AppSessionLocal() as session:
        # Get recent chat logs
        q = select(ChatLog).order_by(ChatLog.timestamp.desc()).limit(5)
        logs = (await session.execute(q)).scalars().all()
        for log in logs:
            print(f"Q: {log.question}")
            print(f"SQL: {log.generated_sql}")
            print("-" * 40)
            
        # Check Karen Smith's data
        q = select(Student.name, StudentSummary.attendance_rate, StudentSummary.grade_avg).join(Student, Student.id == StudentSummary.student_id).where(Student.name.like("%Karen Smith%"))
        karen = (await session.execute(q)).first()
        print(f"Karen Smith: {karen}")
            
asyncio.run(main())
