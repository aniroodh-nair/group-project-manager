import json
import os
from datetime import datetime

from flask import Flask, render_template, request, url_for

app = Flask(__name__)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
DATA_FILE = os.path.join(DATA_DIR, "profiles.json")


def _load_profiles():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def _save_profiles(profiles):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as file:
        json.dump(profiles, file, indent=2)


@app.route("/profile", methods=["GET", "POST"])
def profile():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        skills = request.form.get("skills", "").strip()
        role = request.form.get("role", "").strip()

        if not name or not email or not skills or not role:
            error = "Please complete all fields before submitting."
            return render_template(
                "profile.html",
                error=error,
                form_data={
                    "name": name,
                    "email": email,
                    "skills": skills,
                    "role": role,
                },
            )

        profiles = _load_profiles()
        profiles.append(
            {
                "name": name,
                "email": email,
                "skills": skills,
                "role": role,
                "submitted_at": datetime.utcnow().isoformat() + "Z",
            }
        )
        _save_profiles(profiles)

        from flask import redirect, url_for
        return redirect(url_for("view_profiles"))

    return render_template("profile.html", form_data={})

@app.route("/profiles")
def view_profiles():
    profiles = _load_profiles()
    return render_template("profiles.html", profiles=profiles)

if __name__ == "__main__":
    app.run(debug=True)