from flask import render_template
from flask import Flask, jsonify
from backend.models import db
from backend.services.grouping_service import get_students, create_groups, save_groups

app = Flask(__name__)

# Database config
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

# Create tables automatically
with app.app_context():
    db.create_all()


# Test route
@app.route("/")
def home():
    return render_template("index.html")


# Group generation route
@app.route("/generate-groups")
def generate_groups():
    students = get_students()
    groups = create_groups(students, 4)
    save_groups(groups)
    return jsonify({"message": "Groups created successfully"})


# IMPORTANT PART (server start)
if __name__ == "__main__":
    app.run(debug=True)