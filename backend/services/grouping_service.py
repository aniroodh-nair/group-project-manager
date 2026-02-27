from backend.models import Student
from collections import defaultdict
import random

def get_students():
    students = Student.query.all()
    data = []
    for s in students:
        data.append({
            "id": s.id,
            "name": s.name,
            "skills": s.skills.split(",")
        })
    return data
def create_groups(students, group_size, shuffle=False):
    if not students:
        return []
    
    num_groups = len(students) // group_size
    if num_groups == 0:
        num_groups = 1
    
    groups = [[] for _ in range(num_groups)]

    if shuffle:
        # Shuffle students randomly
        random.shuffle(students)
        # Distribute randomly
        for i, student in enumerate(students):
            groups[i % num_groups].append(student)
    else:
        # classify by main skill
        skill_buckets = defaultdict(list)
        for s in students:
            skill_buckets[s["skills"][0]].append(s)

        # round robin distribute
        index = 0
        for skill in skill_buckets:
            for student in skill_buckets[skill]:
                groups[index % num_groups].append(student)
                index += 1

    return groups

from backend.models import db, ProjectGroup, GroupMember

def save_groups(groups):
    for g in groups:
        group = ProjectGroup()
        db.session.add(group)
        db.session.flush()

        for student in g:
            member = GroupMember(student_id=student["id"], group_id=group.id)
            db.session.add(member)

    db.session.commit()
