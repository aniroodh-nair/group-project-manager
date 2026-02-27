class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50))
    skills = db.Column(db.String(200))   # "python,design,documentation"

class ProjectGroup(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class GroupMember(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'))
    group_id = db.Column(db.Integer, db.ForeignKey('project_group.id'))

