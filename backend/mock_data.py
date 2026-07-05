import os
from faker import Faker
from sqlalchemy.orm import Session
import random
from datetime import datetime, timedelta, date

from database import engine, Base, SessionLocal
from models import (User, RoleEnum, Department, Teacher, Course, ClassInstance, 
                    Student, Enrollment, Attendance, Assignment, Grade, FeeInvoice, Payment, Alert)

fake = Faker()

def create_mock_data():
    print("Creating tables...")
    Base.metadata.create_all(bind=engine)
    
    db: Session = SessionLocal()
    
    try:
        if db.query(User).first():
            print("Database already has data. Skipping mock generation.")
            return

        print("Generating mock data...")

        # 1. Create Admins
        admin_user = User(username="admin", email="admin@school.edu", role=RoleEnum.ADMIN)
        db.add(admin_user)
        db.commit()

        # 2. Create Departments
        dept_names = ["Mathematics", "Science", "Arts", "History", "Physical Education"]
        departments = []
        for name in dept_names:
            dept = Department(name=name)
            db.add(dept)
            departments.append(dept)
        db.commit()

        # 3. Create Teachers
        teachers = []
        for _ in range(10):
            t_user = User(
                username=fake.user_name(), 
                email=fake.email(), 
                role=RoleEnum.TEACHER
            )
            db.add(t_user)
            db.commit()
            
            teacher = Teacher(
                user_id=t_user.id,
                department_id=random.choice(departments).id,
                hire_date=fake.date_between(start_date='-5y', end_date='today')
            )
            db.add(teacher)
            teachers.append(teacher)
        db.commit()

        # 4. Create Courses
        courses = []
        for i in range(20):
            dept = random.choice(departments)
            course = Course(
                department_id=dept.id,
                code=f"{dept.name[:3].upper()}{random.randint(100, 499)}",
                name=f"{dept.name} - Level {random.randint(1,4)}",
                credits=random.choice([3, 4])
            )
            db.add(course)
            courses.append(course)
        db.commit()

        # 5. Create Classes
        classes = []
        for _ in range(30):
            cls = ClassInstance(
                course_id=random.choice(courses).id,
                teacher_id=random.choice(teachers).id,
                semester="Fall 2026",
                room_number=f"Room {random.randint(101, 305)}"
            )
            db.add(cls)
            classes.append(cls)
        db.commit()

        # 6. Create Students
        students = []
        for _ in range(100):
            s_user = User(
                username=fake.user_name(),
                email=fake.email(),
                role=RoleEnum.STUDENT
            )
            db.add(s_user)
            db.commit()

            student = Student(
                user_id=s_user.id,
                enrollment_date=fake.date_between(start_date='-2y', end_date='today'),
                date_of_birth=fake.date_of_birth(minimum_age=14, maximum_age=18),
                gpa=round(random.uniform(2.0, 4.0), 2)
            )
            db.add(student)
            students.append(student)
        db.commit()

        # 7. Create Enrollments
        enrollments = []
        for student in students:
            # Each student takes 4-6 classes
            enrolled_classes = random.sample(classes, random.randint(4, 6))
            for cls in enrolled_classes:
                enroll = Enrollment(
                    student_id=student.id,
                    class_id=cls.id,
                    enrollment_date=date(2026, 8, 1)
                )
                db.add(enroll)
                enrollments.append(enroll)
        db.commit()

        # 8. Create Assignments and Grades
        for cls in classes:
            # Create 3 assignments per class
            for i in range(3):
                assignment = Assignment(
                    class_id=cls.id,
                    title=f"Assignment {i+1}",
                    description=fake.text(max_nb_chars=100),
                    due_date=datetime.utcnow() - timedelta(days=random.randint(1, 30)),
                    max_points=100
                )
                db.add(assignment)
                db.commit()

                # Grade students enrolled in this class
                class_enrollments = [e for e in enrollments if e.class_id == cls.id]
                for enroll in class_enrollments:
                    grade = Grade(
                        student_id=enroll.student_id,
                        assignment_id=assignment.id,
                        points_earned=random.uniform(50.0, 100.0)
                    )
                    db.add(grade)
        db.commit()

        # 9. Create Attendance
        for cls in classes:
            class_enrollments = [e for e in enrollments if e.class_id == cls.id]
            # Simulate 10 days of attendance
            for i in range(10):
                att_date = date.today() - timedelta(days=i)
                for enroll in class_enrollments:
                    status = random.choices(["Present", "Absent", "Late"], weights=[85, 10, 5])[0]
                    att = Attendance(
                        student_id=enroll.student_id,
                        class_id=cls.id,
                        date=att_date,
                        status=status
                    )
                    db.add(att)
        db.commit()

        # 10. Create Fee Invoices & Payments
        for student in students:
            invoice = FeeInvoice(
                student_id=student.id,
                description="Fall 2026 Tuition",
                amount=5000.0,
                due_date=date(2026, 9, 1),
                status=random.choice(["Unpaid", "Partial", "Paid"])
            )
            db.add(invoice)
            db.commit()

            if invoice.status == "Paid":
                payment = Payment(
                    invoice_id=invoice.id,
                    amount_paid=5000.0,
                    method=random.choice(["Credit Card", "Bank Transfer", "Cash"])
                )
                db.add(payment)
            elif invoice.status == "Partial":
                payment = Payment(
                    invoice_id=invoice.id,
                    amount_paid=random.uniform(1000.0, 4000.0),
                    method=random.choice(["Credit Card", "Bank Transfer", "Cash"])
                )
                db.add(payment)
        db.commit()

        # 11. Create some initial alerts
        alert1 = Alert(
            target_role=RoleEnum.ADMIN,
            title="Low Attendance Warning",
            message="15 students have attendance below 75% in the last 2 weeks."
        )
        alert2 = Alert(
            target_role=RoleEnum.ADMIN,
            title="Unpaid Fees",
            message=f"{db.query(FeeInvoice).filter(FeeInvoice.status != 'Paid').count()} students have outstanding fees for Fall 2026."
        )
        db.add_all([alert1, alert2])
        db.commit()

        print("Mock data generated successfully!")

    except Exception as e:
        print(f"Error generating data: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    create_mock_data()
