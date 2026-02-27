from flask import render_template, request
from flask import Flask, jsonify
from backend.models import db, Student
from backend.services.grouping_service import get_students, create_groups, save_groups

app = Flask(__name__)

# Database config
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

# Create tables automatically
with app.app_context():
    db.create_all()
    
    # Add sample students if database is empty
    if Student.query.count() == 0:
        sample_students = [
            Student(name="Alice Johnson", skills="python,design,communication"),
            Student(name="Bob Smith", skills="javascript,backend,testing"),
            Student(name="Charlie Brown", skills="python,frontend,design"),
            Student(name="Diana Prince", skills="javascript,documentation,communication"),
            Student(name="Eve Wilson", skills="python,testing,documentation"),
            Student(name="Frank Miller", skills="javascript,design,backend"),
            Student(name="Grace Lee", skills="python,communication,frontend"),
            Student(name="Henry Davis", skills="javascript,testing,design"),
        ]
        db.session.add_all(sample_students)
        db.session.commit()


# Test route
@app.route("/")
def home():
    return render_template("index.html")


# Group generation route
@app.route("/generate-groups")
def generate_groups():
    shuffle = request.args.get('shuffle', 'false').lower() == 'true'
    students = get_students()
    groups = create_groups(students, 4, shuffle=shuffle)
    save_groups(groups)
    return jsonify({"message": "Groups created successfully", "groups": groups})


# IMPORTANT PART (server start)
if __name__ == "__main__":
    app.run(debug=True)