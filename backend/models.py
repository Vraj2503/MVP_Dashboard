from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Date, DateTime, Float, Text, Enum
from sqlalchemy.orm import relationship
from database import Base
import enum
from datetime import datetime

class RoleEnum(enum.Enum):
    ADMIN = "admin"
    TEACHER = "teacher"
    STUDENT = "student"
    PARENT = "parent"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    role = Column(Enum(RoleEnum), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    student_profile = relationship("Student", back_populates="user", uselist=False)
    teacher_profile = relationship("Teacher", back_populates="user", uselist=False)

class Department(Base):
    __tablename__ = "departments"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    
    courses = relationship("Course", back_populates="department")
    teachers = relationship("Teacher", back_populates="department")

class Teacher(Base):
    __tablename__ = "teachers"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    department_id = Column(Integer, ForeignKey("departments.id"))
    hire_date = Column(Date)
    
    user = relationship("User", back_populates="teacher_profile")
    department = relationship("Department", back_populates="teachers")
    classes = relationship("ClassInstance", back_populates="teacher")

class Course(Base):
    __tablename__ = "courses"
    id = Column(Integer, primary_key=True, index=True)
    department_id = Column(Integer, ForeignKey("departments.id"))
    code = Column(String(20), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    credits = Column(Integer, default=3)
    
    department = relationship("Department", back_populates="courses")
    classes = relationship("ClassInstance", back_populates="course")

class ClassInstance(Base):
    __tablename__ = "classes"
    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    teacher_id = Column(Integer, ForeignKey("teachers.id"), nullable=False)
    semester = Column(String(20), nullable=False) # e.g., "Fall 2026"
    room_number = Column(String(20))
    
    course = relationship("Course", back_populates="classes")
    teacher = relationship("Teacher", back_populates="classes")
    enrollments = relationship("Enrollment", back_populates="class_instance")
    assignments = relationship("Assignment", back_populates="class_instance")
    attendance = relationship("Attendance", back_populates="class_instance")

class Student(Base):
    __tablename__ = "students"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    enrollment_date = Column(Date)
    date_of_birth = Column(Date)
    gpa = Column(Float, default=0.0)
    
    user = relationship("User", back_populates="student_profile")
    enrollments = relationship("Enrollment", back_populates="student")
    attendance = relationship("Attendance", back_populates="student")
    grades = relationship("Grade", back_populates="student")
    invoices = relationship("FeeInvoice", back_populates="student")

class Enrollment(Base):
    __tablename__ = "enrollments"
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False)
    enrollment_date = Column(Date)
    
    student = relationship("Student", back_populates="enrollments")
    class_instance = relationship("ClassInstance", back_populates="enrollments")

class Attendance(Base):
    __tablename__ = "attendance"
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False)
    date = Column(Date, nullable=False)
    status = Column(String(20), nullable=False) # Present, Absent, Late, Excused
    
    student = relationship("Student", back_populates="attendance")
    class_instance = relationship("ClassInstance", back_populates="attendance")

class Assignment(Base):
    __tablename__ = "assignments"
    id = Column(Integer, primary_key=True, index=True)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False)
    title = Column(String(100), nullable=False)
    description = Column(Text)
    due_date = Column(DateTime)
    max_points = Column(Integer, default=100)
    
    class_instance = relationship("ClassInstance", back_populates="assignments")
    grades = relationship("Grade", back_populates="assignment")

class Grade(Base):
    __tablename__ = "grades"
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    assignment_id = Column(Integer, ForeignKey("assignments.id"), nullable=False)
    points_earned = Column(Float, nullable=False)
    date_graded = Column(DateTime, default=datetime.utcnow)
    
    student = relationship("Student", back_populates="grades")
    assignment = relationship("Assignment", back_populates="grades")

class FeeInvoice(Base):
    __tablename__ = "fee_invoices"
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    description = Column(String(255), nullable=False)
    amount = Column(Float, nullable=False)
    due_date = Column(Date, nullable=False)
    status = Column(String(20), default="Unpaid") # Unpaid, Partial, Paid
    
    student = relationship("Student", back_populates="invoices")
    payments = relationship("Payment", back_populates="invoice")

class Payment(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("fee_invoices.id"), nullable=False)
    amount_paid = Column(Float, nullable=False)
    payment_date = Column(DateTime, default=datetime.utcnow)
    method = Column(String(50)) # Credit Card, Bank Transfer, Cash
    
    invoice = relationship("FeeInvoice", back_populates="payments")

class Alert(Base):
    __tablename__ = "alerts"
    id = Column(Integer, primary_key=True, index=True)
    target_role = Column(Enum(RoleEnum), nullable=False)
    title = Column(String(100), nullable=False)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_read = Column(Boolean, default=False)
