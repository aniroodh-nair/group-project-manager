from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


# STUDENT TABLE
class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50))
    skills = db.Column(db.String(200))   # "python,design,presentation"


# GROUP TABLE
class ProjectGroup(db.Model):
    id = db.Column(db.Integer, primary_key=True)


# GROUP MEMBERS TABLE
class GroupMember(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer)
    group_id = db.Column(db.Integer)