
import json
import os
import random
from collections import Counter
from datetime import datetime
from datetime import timedelta
from datetime import timezone

from flask import Flask, redirect, render_template, request, url_for, session, jsonify, send_from_directory
from werkzeug.utils import secure_filename

from .auth import (
    require_login,
    require_role,
    get_current_user,
    login_user,
    register_user,
    load_users,
)

from .services.shuffling_algorithm import shuffle_into_groups, suggest_group_improvements

app = Flask(__name__)
app.secret_key = "your-secret-key-change-in-production"

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
DATA_FILE = os.path.join(DATA_DIR, "profiles.json")
SUBMISSIONS_UPLOAD_DIR = os.path.join(DATA_DIR, "submission_uploads")
MONTHLY_GOAL = 30
PROJECT_MEMBER_ROLES = [
    "Team Leader",
    "Presenter",
    "Documentation Lead",
    "Researcher",
    "Tester / QA",
    "Coder (Frontend)",
    "Coder (Backend)",
    "UI/UX Designer",
]


def _load_profiles():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def _save_profiles(profiles):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as file:
        json.dump(profiles, file, indent=2)


def _parse_iso_datetime(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _normalize_email(email):
    return (email or "").strip().lower()


def _normalize_name(name):
    return " ".join((name or "").strip().lower().split())


def _extract_member_email(member):
    if isinstance(member, str):
        return member
    if isinstance(member, dict):
        return member.get("email", "")
    return ""


def _get_user_alias_emails(user, profiles=None):
    aliases = {_normalize_email(user.get("email"))}
    if profiles is None:
        profiles = _load_profiles()

    user_name = _normalize_name(user.get("name"))
    if not user_name:
        return aliases

    for profile in profiles:
        if _normalize_name(profile.get("name")) == user_name:
            aliases.add(_normalize_email(profile.get("email")))

    return aliases


def _is_group_member(group, email):
    normalized_email = _normalize_email(email)
    members = group.get("members", [])
    member_emails = {_normalize_email(_extract_member_email(member)) for member in members}
    return normalized_email in member_emails


def _is_group_member_by_aliases(group, alias_emails):
    members = group.get("members", [])
    member_emails = {_normalize_email(_extract_member_email(member)) for member in members}
    return bool(member_emails.intersection(alias_emails))


def _assign_member_project_roles(members):
    role_pool = PROJECT_MEMBER_ROLES.copy()
    random.shuffle(role_pool)

    assignments = {}
    for index, member in enumerate(members):
        member_email = _normalize_email(_extract_member_email(member))
        if not member_email:
            continue

        if index < len(role_pool):
            assignments[member_email] = role_pool[index]
        else:
            assignments[member_email] = f"Member {index + 1}"

    return assignments


def _get_group_member_email_set(group):
    return {
        _normalize_email(_extract_member_email(member))
        for member in group.get("members", [])
        if _extract_member_email(member)
    }


def _get_group_leader_aliases(group):
    leaders = set()
    for email, assigned_role in group.get("member_project_roles", {}).items():
        if (assigned_role or "").strip().lower() == "team leader":
            leaders.add(_normalize_email(email))
    return leaders


def _load_groups():
    """Load groups from JSON"""
    groups_file = os.path.join(DATA_DIR, "groups.json")
    if not os.path.exists(groups_file):
        return []
    with open(groups_file, "r", encoding="utf-8") as file:
        return json.load(file)


def _save_groups(groups):
    """Save groups to JSON"""
    os.makedirs(DATA_DIR, exist_ok=True)
    groups_file = os.path.join(DATA_DIR, "groups.json")
    with open(groups_file, "w", encoding="utf-8") as file:
        json.dump(groups, file, indent=2)


def _load_comments():
    """Load feedback comments from JSON"""
    comments_file = os.path.join(DATA_DIR, "comments.json")
    if not os.path.exists(comments_file):
        return []
    with open(comments_file, "r", encoding="utf-8") as file:
        return json.load(file)


def _save_comments(comments):
    """Save feedback comments to JSON"""
    os.makedirs(DATA_DIR, exist_ok=True)
    comments_file = os.path.join(DATA_DIR, "comments.json")
    with open(comments_file, "w", encoding="utf-8") as file:
        json.dump(comments, file, indent=2)


def _load_submissions():
    submissions_file = os.path.join(DATA_DIR, "submissions.json")
    if not os.path.exists(submissions_file):
        return []
    with open(submissions_file, "r", encoding="utf-8") as file:
        return json.load(file)


def _save_submissions(submissions):
    os.makedirs(DATA_DIR, exist_ok=True)
    submissions_file = os.path.join(DATA_DIR, "submissions.json")
    with open(submissions_file, "w", encoding="utf-8") as file:
        json.dump(submissions, file, indent=2)


def _save_submission_file(uploaded_file):
    if not uploaded_file or not uploaded_file.filename:
        return None, None

    original_name = secure_filename(uploaded_file.filename)
    if not original_name:
        return None, None

    os.makedirs(SUBMISSIONS_UPLOAD_DIR, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    stored_name = f"{timestamp}_{original_name}"
    uploaded_file.save(os.path.join(SUBMISSIONS_UPLOAD_DIR, stored_name))
    return stored_name, original_name


def _build_department_students(department):
    profiles = _load_profiles()
    users = load_users()

    profile_by_email = {
        _normalize_email(profile.get("email")): profile for profile in profiles
    }

    department_students = []
    for user_data in users.values():
        if user_data.get("role") != "student":
            continue
        if user_data.get("department") != department:
            continue

        email = user_data.get("email", "")
        profile = profile_by_email.get(_normalize_email(email), {})

        department_students.append(
            {
                "name": profile.get("name") or user_data.get("name") or email,
                "email": email,
                "role": profile.get("role") or "Student",
                "skills": profile.get("skills") or user_data.get("specialization") or "",
                "department": department,
            }
        )

    return department_students


@app.route("/login", methods=["GET", "POST"])
def login_page():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        
        success, result = login_user(email, password)
        if success:
            session["user_email"] = email
            session["user_name"] = result["name"]
            session["user_role"] = result["role"]
            return redirect(url_for("dashboard"))
        else:
            return render_template("login.html", error=result)
    
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register_page():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        name = request.form.get("name", "").strip()
        role = request.form.get("role", "student").strip()
        department = request.form.get("department", "").strip()
        specialization = request.form.get("specialization", "").strip()
        
        if not email or not password or not name:
            return render_template("register.html", error="All fields required")
        
        success, message = register_user(email, password, name, role, department, specialization)
        if success:
            return render_template("register.html", success="Registration successful! Please login.")
        else:
            return render_template("register.html", error=message)
    
    return render_template("register.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login_page"))


@app.route("/")
def home():
    if "user_email" not in session:
        return redirect(url_for("login_page"))
    return redirect(url_for("dashboard"))


@app.route("/dashboard")
@require_login
def dashboard():
    """Route users to their role-specific dashboard"""
    user_role = session.get("user_role")
    
    if user_role == "student":
        return redirect(url_for("student_dashboard"))
    elif user_role in ["faculty", "hod", "admin"]:
        return redirect(url_for("faculty_dashboard"))
    else:
        return redirect(url_for("view_profiles"))


@app.route("/student/dashboard")
@require_login
def student_dashboard():
    """Student view: see assigned projects/groups and progress"""
    user = get_current_user()
    profiles = _load_profiles()
    alias_emails = _get_user_alias_emails(user, profiles)

    all_groups = _load_groups()
    groups = [g for g in all_groups if _is_group_member_by_aliases(g, alias_emails)]
    
    return render_template(
        "student_dashboard.html",
        user=user,
        groups=groups,
        profiles=profiles
    )


@app.route("/faculty/dashboard")
@require_login
def faculty_dashboard():
    """Faculty/Teacher view: manage students, groups, and feedback"""
    user = get_current_user()
    profiles = _load_profiles()
    groups = _load_groups()
    comments = _load_comments()
    submissions = _load_submissions()

    dept_students = _build_department_students(user.get("department"))

    for student in dept_students:
        if not student.get("skills"):
            student["skills"] = "-"

    dept_student_emails = {_normalize_email(student.get("email")) for student in dept_students}
    role_counter = Counter(student.get("role", "Unknown") for student in dept_students)

    group_lookup = {group.get("id"): group for group in groups}
    faculty_submissions = []
    for submission in submissions:
        student_email = _normalize_email(submission.get("student_email"))
        if student_email not in dept_student_emails:
            continue

        group_id = submission.get("group_id")
        group = group_lookup.get(group_id, {})

        faculty_submissions.append(
            {
                **submission,
                "group_name": group.get("name", f"Group {group_id}" if group_id else "Unknown Group"),
                "project_title": group.get("project_title", ""),
            }
        )

    faculty_submissions.sort(
        key=lambda submission: submission.get("submitted_at", ""),
        reverse=True,
    )
    
    return render_template(
        "faculty_dashboard.html",
        user=user,
        profiles=dept_students,
        groups=groups,
        comments=comments,
        submissions=faculty_submissions,
        role_labels=list(role_counter.keys()),
        role_values=list(role_counter.values()),
    )


@app.route("/grade/add", methods=["POST"])
@require_login
def add_grade():
    """Faculty add grade to group"""
    group_id = request.form.get("group_id", "").strip()
    score = request.form.get("score", "").strip()
    max_score = request.form.get("max_score", "100").strip()
    remarks = request.form.get("remarks", "").strip()
    
    if not group_id or not score:
        return {"error": "Missing details"}, 400
    
    user = get_current_user()
    groups = _load_groups()
    group = next((g for g in groups if g["id"] == int(group_id)), None)
    
    if not group:
        return "Group not found", 404
    
    # Add or update grade in group
    if "grade" not in group:
        group["grade"] = {}
    
    group["grade"] = {
        "score": float(score),
        "max_score": float(max_score),
        "remarks": remarks,
        "faculty_email": user["email"],
        "faculty_name": user["name"],
        "graded_at": datetime.now(timezone.utc).isoformat()
    }
    
    _save_groups(groups)
    return redirect(url_for("view_group_detail", group_id=int(group_id)))


@app.route("/feedback/add", methods=["POST"])
@require_login
def add_feedback():
    """Faculty/HOD add feedback to student"""
    student_email = request.form.get("student_email", "").strip()
    comment = request.form.get("comment", "").strip()
    comment_type = request.form.get("type", "general").strip()  # general, grade, improvement
    group_id = request.form.get("group_id", "").strip()
    
    if not student_email or not comment:
        return {"error": "Missing details"}, 400
    
    user = get_current_user()
    comments = _load_comments()
    
    comments.append({
        "id": len(comments) + 1,
        "student_email": student_email,
        "faculty_email": user["email"],
        "faculty_name": user["name"],
        "comment": comment,
        "type": comment_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "group_id": int(group_id) if group_id else None
    })
    
    _save_comments(comments)
    
    # Redirect back to group detail if group_id provided, otherwise to faculty dashboard
    if group_id:
        return redirect(url_for("view_group_detail", group_id=int(group_id)))
    return redirect(url_for("faculty_dashboard"))


@app.route("/feedback/student/<email>")
@require_login
def get_student_feedback(email):
    """Get all feedback for a student"""
    comments = _load_comments()
    student_comments = [c for c in comments if c.get("student_email") == email]
    return render_template(
        "feedback.html",
        student_email=email,
        comments=student_comments
    )


@app.route("/feedback/history")
@require_role("student")
def my_feedback():
    """Student view their own feedback"""
    user = get_current_user()
    comments = _load_comments()
    my_comments = [c for c in comments if c.get("student_email") == user["email"]]
    
    return render_template(
        "my_feedback.html",
        comments=my_comments
    )


@app.route("/profile", methods=["GET", "POST"])
@require_login
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
                is_edit=False,
                form_data={
                    "name": name,
                    "email": email,
                    "skills": skills,
                    "role": role,
                },
            )

        profiles = _load_profiles()
        if any(p["email"] == email for p in profiles):
            error = "A profile with this email already exists."
            return render_template(
                "profile.html",
                error=error,
                is_edit=False,
                form_data={
                    "name": name,
                    "email": email,
                    "skills": skills,
                    "role": role,
                },
            )

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
        return redirect(url_for("view_profiles"))

    return render_template("profile.html", form_data={}, is_edit=False)


@app.route("/edit", methods=["GET", "POST"])
@require_login
def edit_profile():
    if request.method == "POST":
        original_email = request.form.get("original_email", "").strip()
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        skills = request.form.get("skills", "").strip()
        role = request.form.get("role", "").strip()

        if not original_email or not name or not email or not skills or not role:
            error = "Please complete all fields before saving."
            return render_template(
                "profile.html",
                error=error,
                is_edit=True,
                form_data={
                    "name": name,
                    "email": email,
                    "skills": skills,
                    "role": role,
                    "original_email": original_email,
                },
            )

        profiles = _load_profiles()
        profile_index = next(
            (index for index, profile in enumerate(profiles) if profile["email"] == original_email),
            None,
        )

        if profile_index is None:
            return redirect(url_for("view_profiles"))

        if email != original_email and any(p["email"] == email for p in profiles):
            error = "Another profile with this email already exists."
            return render_template(
                "profile.html",
                error=error,
                is_edit=True,
                form_data={
                    "name": name,
                    "email": email,
                    "skills": skills,
                    "role": role,
                    "original_email": original_email,
                },
            )

        profiles[profile_index].update(
            {
                "name": name,
                "email": email,
                "skills": skills,
                "role": role,
                "updated_at": datetime.utcnow().isoformat() + "Z",
            }
        )

        _save_profiles(profiles)
        return redirect(url_for("view_profiles"))

    email = request.args.get("email", "").strip()
    profiles = _load_profiles()
    profile_data = next((profile for profile in profiles if profile["email"] == email), None)

    if not profile_data:
        return redirect(url_for("view_profiles"))

    return render_template(
        "profile.html",
        form_data={
            "name": profile_data.get("name", ""),
            "email": profile_data.get("email", ""),
            "skills": profile_data.get("skills", ""),
            "role": profile_data.get("role", ""),
            "original_email": profile_data.get("email", ""),
        },
        is_edit=True,
    )


@app.route("/delete", methods=["POST"])
@require_login
def delete_profile():
    email = request.form.get("email")

    profiles = _load_profiles()
    profiles = [p for p in profiles if p["email"] != email]

    _save_profiles(profiles)

    return redirect(url_for("view_profiles"))

@app.route("/profiles")
@require_login
def view_profiles():
    profiles = _load_profiles()

    role_counter = Counter(profile.get("role", "Unknown") for profile in profiles)
    total_coders = sum(
        1 for profile in profiles if "coder" in profile.get("role", "").strip().lower()
    )
    backend_coders = sum(
        1
        for profile in profiles
        if profile.get("role", "").strip().lower() == "coder (backend)"
    )
    frontend_coders = sum(
        1
        for profile in profiles
        if profile.get("role", "").strip().lower() == "coder (frontend)"
    )

    top_skills = Counter()
    for profile in profiles:
        skills = profile.get("skills", "")
        for skill in skills.split(","):
            skill_name = skill.strip()
            if skill_name:
                top_skills[skill_name] += 1

    top_skill_items = top_skills.most_common(10)
    max_skill_count = top_skill_items[0][1] if top_skill_items else 1
    skill_stats = [
        {
            "name": skill_name,
            "count": count,
            "percentage": int((count / max_skill_count) * 100),
        }
        for skill_name, count in top_skill_items
    ]

    today = datetime.now(timezone.utc).date()
    last_7_days = [today - timedelta(days=offset) for offset in range(6, -1, -1)]
    submissions_by_day = {day: 0 for day in last_7_days}

    for profile in profiles:
        submitted_dt = _parse_iso_datetime(profile.get("submitted_at"))
        if submitted_dt:
            submitted_date = submitted_dt.date()
            if submitted_date in submissions_by_day:
                submissions_by_day[submitted_date] += 1

    submission_labels = [day.strftime("%b %d") for day in last_7_days]
    submission_values = [submissions_by_day[day] for day in last_7_days]

    current_month_count = 0
    for profile in profiles:
        submitted_dt = _parse_iso_datetime(profile.get("submitted_at"))
        if submitted_dt and submitted_dt.year == today.year and submitted_dt.month == today.month:
            current_month_count += 1

    monthly_progress = min(int((current_month_count / MONTHLY_GOAL) * 100), 100)

    recent_profiles = sorted(
        profiles,
        key=lambda profile: profile.get("submitted_at", ""),
        reverse=True,
    )[:5]

    chart_role_labels = list(role_counter.keys())
    chart_role_values = list(role_counter.values())

    return render_template(
        "profiles.html",
        profiles=profiles,
        total_coders=total_coders,
        backend_coders=backend_coders,
        frontend_coders=frontend_coders,
        role_counter=role_counter,
        chart_role_labels=chart_role_labels,
        chart_role_values=chart_role_values,
        submission_labels=submission_labels,
        submission_values=submission_values,
        skill_stats=skill_stats,
        recent_profiles=recent_profiles,
        current_month_count=current_month_count,
        monthly_goal=MONTHLY_GOAL,
        monthly_progress=monthly_progress,
    )


@app.route("/profile-detail")
@require_login
def profile_detail():
    email = request.args.get("email", "").strip()
    profiles = _load_profiles()
    profile_data = next((profile for profile in profiles if profile["email"] == email), None)

    if not profile_data:
        return redirect(url_for("view_profiles"))

    return render_template("profile_detail.html", profile=profile_data)


# Group Management Routes
@app.route("/group/create", methods=["POST"])
@require_login
def create_group():
    """Create a new group"""
    group_name = request.form.get("name", "").strip()
    members = request.form.getlist("members")  # List of student emails
    project_title = request.form.get("project_title", "").strip()
    
    groups = _load_groups()
    new_group = {
        "id": len(groups) + 1,
        "name": group_name,
        "project_title": project_title,
        "members": members,
        "member_project_roles": _assign_member_project_roles(members),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "active"  # active, paused, completed
    }
    groups.append(new_group)
    _save_groups(groups)
    
    return redirect(url_for("faculty_dashboard"))

@app.route("/group/<int:group_id>/shuffle", methods=["POST"])
@require_login
def shuffle_group(group_id):
    """Shuffle/rebalance members in a group"""

    groups = _load_groups()
    group = next((g for g in groups if g["id"] == group_id), None)
    
    if not group:
        return "Group not found", 404
    
    # Shuffle the members
    members = group.get("members", [])
    random.shuffle(members)
    group["members"] = members
    group["member_project_roles"] = _assign_member_project_roles(members)
    group["last_shuffled"] = datetime.now(timezone.utc).isoformat()
    
    _save_groups(groups)
    return redirect(url_for("faculty_dashboard"))


@app.route("/group/<int:group_id>/update-status", methods=["POST"])
@require_login
def update_group_status(group_id):
    """Update group status (active, paused, completed)"""
    new_status = request.form.get("status", "").strip()
    
    groups = _load_groups()
    group = next((g for g in groups if g["id"] == group_id), None)
    
    if not group:
        return {"error": "Group not found"}, 404
    
    if new_status not in ["active", "paused", "completed"]:
        return {"error": "Invalid status"}, 400
    
    group["status"] = new_status
    _save_groups(groups)
    
    return redirect(url_for("faculty_dashboard"))


@app.route("/group/<int:group_id>/view")
@require_login
def view_group_detail(group_id):
    """View detailed group information"""
    user = get_current_user()
    groups = _load_groups()
    group = next((g for g in groups if g["id"] == group_id), None)
    
    if not group:
        return "Group not found", 404

    profiles = _load_profiles()
    alias_emails = _get_user_alias_emails(user, profiles)

    if user.get("role") == "student" and not _is_group_member_by_aliases(group, alias_emails):
        return "Access Denied", 403

    can_submit_work = user.get("role") == "student" and _is_group_member_by_aliases(group, alias_emails)
    can_manage_tasks = bool(alias_emails.intersection(_get_group_leader_aliases(group)))
    
    # Load member details
    profile_by_email = {_normalize_email(profile.get("email")): profile for profile in profiles}
    assigned_roles = {
        _normalize_email(email): role
        for email, role in group.get("member_project_roles", {}).items()
    }
    members_details = []
    for email in group.get("members", []):
        normalized_email = _normalize_email(_extract_member_email(email))
        member = profile_by_email.get(normalized_email)

        if member:
            member_payload = dict(member)
        else:
            member_payload = {
                "name": normalized_email,
                "email": normalized_email,
                "role": "Student",
                "skills": "",
            }

        member_payload["assigned_group_role"] = assigned_roles.get(normalized_email)
        members_details.append(member_payload)
    
    # Load comments for this group
    comments = _load_comments()
    group_comments = [c for c in comments if c.get("group_id") == group_id]

    submissions = _load_submissions()
    group_submissions = [s for s in submissions if s.get("group_id") == group_id]
    group_submissions.sort(key=lambda submission: submission.get("submitted_at", ""), reverse=True)

    group_tasks = group.get("tasks", [])
    group_tasks.sort(key=lambda task: task.get("created_at", ""), reverse=True)
    
    return render_template(
        "group_detail.html",
        user=user,
        group=group,
        members=members_details,
        comments=group_comments,
        submissions=group_submissions,
        tasks=group_tasks,
        can_submit_work=can_submit_work,
        can_manage_tasks=can_manage_tasks,
    )


@app.route("/group/<int:group_id>/tasks/add", methods=["POST"])
@require_login
def add_group_task(group_id):
    user = get_current_user()
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    assigned_to = _normalize_email(request.form.get("assigned_to", "").strip())
    due_date = request.form.get("due_date", "").strip()
    priority = request.form.get("priority", "medium").strip().lower()

    if not title or not assigned_to:
        return "Task title and assignee are required", 400

    groups = _load_groups()
    group = next((g for g in groups if g.get("id") == group_id), None)
    if not group:
        return "Group not found", 404

    alias_emails = _get_user_alias_emails(user)
    leader_aliases = _get_group_leader_aliases(group)
    if not alias_emails.intersection(leader_aliases):
        return "Only the assigned Team Leader can split/assign work", 403

    member_emails = _get_group_member_email_set(group)
    if assigned_to not in member_emails:
        return "Assignee must be a member of this group", 400

    if priority not in ["low", "medium", "high"]:
        priority = "medium"

    users = load_users()
    profiles = _load_profiles()
    profile_by_email = {_normalize_email(profile.get("email")): profile for profile in profiles}

    assigned_user = users.get(assigned_to, {})
    assigned_profile = profile_by_email.get(assigned_to, {})
    assigned_name = (
        assigned_profile.get("name")
        or assigned_user.get("name")
        or assigned_to
    )

    if "tasks" not in group:
        group["tasks"] = []

    group["tasks"].append(
        {
            "id": len(group["tasks"]) + 1,
            "title": title,
            "description": description,
            "assigned_to": assigned_to,
            "assigned_to_name": assigned_name,
            "due_date": due_date,
            "priority": priority,
            "status": "pending",
            "created_by": user.get("email"),
            "created_by_name": user.get("name", user.get("email")),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )

    _save_groups(groups)
    return redirect(url_for("view_group_detail", group_id=group_id))


@app.route("/group/<int:group_id>/submit-work", methods=["POST"])
@require_role("student")
def submit_group_work(group_id):
    user = get_current_user()
    submission_link = request.form.get("submission_link", "").strip()
    note = request.form.get("note", "").strip()
    submission_file = request.files.get("submission_file")
    has_file = bool(submission_file and submission_file.filename and submission_file.filename.strip())

    if not submission_link and not has_file:
        return "Provide a submission link or upload a file", 400

    if submission_link and not (submission_link.startswith("http://") or submission_link.startswith("https://")):
        return "Please provide a valid http/https link", 400

    groups = _load_groups()
    group = next((g for g in groups if g["id"] == group_id), None)
    if not group:
        return "Group not found", 404

    alias_emails = _get_user_alias_emails(user)
    if not _is_group_member_by_aliases(group, alias_emails):
        return "Access Denied", 403

    stored_file_name = None
    original_file_name = None
    if has_file:
        stored_file_name, original_file_name = _save_submission_file(submission_file)
        if not stored_file_name:
            return "Invalid file upload", 400

    submissions = _load_submissions()
    submissions.append(
        {
            "id": len(submissions) + 1,
            "group_id": group_id,
            "student_email": user["email"],
            "student_name": user.get("name", user["email"]),
            "submission_link": submission_link,
            "submission_file": stored_file_name,
            "submission_file_name": original_file_name,
            "note": note,
            "submitted_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    _save_submissions(submissions)

    return redirect(url_for("view_group_detail", group_id=group_id))


@app.route("/submission/<int:submission_id>/file")
@require_login
def download_submission_file(submission_id):
    user = get_current_user()
    submissions = _load_submissions()
    submission = next((s for s in submissions if s.get("id") == submission_id), None)

    if not submission or not submission.get("submission_file"):
        return "File not found", 404

    if user.get("role") == "student":
        groups = _load_groups()
        group = next((g for g in groups if g.get("id") == submission.get("group_id")), None)
        if not group:
            return "Group not found", 404

        alias_emails = _get_user_alias_emails(user)
        if not _is_group_member_by_aliases(group, alias_emails):
            return "Access Denied", 403

    return send_from_directory(
        SUBMISSIONS_UPLOAD_DIR,
        submission.get("submission_file"),
        as_attachment=False,
        download_name=submission.get("submission_file_name") or submission.get("submission_file"),
    )


# Intelligent Group Shuffling Routes
@app.route("/group/shuffle/preview", methods=["POST"])
@require_login
def preview_group_shuffle():
    """Preview balanced groups before creating them"""
    num_groups = request.form.get("num_groups", 4, type=int)

    user = get_current_user()
    department_students = _build_department_students(user.get("department"))

    if not department_students:
        return jsonify({"error": "No student profiles available"}), 400
    
    # Generate balanced groups
    balanced_groups = shuffle_into_groups(department_students, num_groups=num_groups)
    
    # Get suggestions for improvements
    suggestions = suggest_group_improvements(balanced_groups)
    
    return jsonify({
        "groups": balanced_groups,
        "suggestions": suggestions,
        "avg_balance_score": sum(g["balance_score"] for g in balanced_groups) / len(balanced_groups) if balanced_groups else 0
    })


@app.route("/group/shuffle/apply", methods=["POST"])
@require_login
def apply_group_shuffle():
    """Apply the balanced groups and save to database"""
    data = request.get_json()
    balanced_groups = data.get("groups", [])
    project_title = data.get("project_title", "Semester Project")
    
    if not balanced_groups:
        return jsonify({"error": "No groups provided"}), 400
    
    # Convert to internal format and save
    groups = []
    for group_data in balanced_groups:
        group = {
            "id": len(groups) + 1,
            "name": group_data.get("name", f"Group {len(groups) + 1}"),
            "members": group_data.get("members", []),
            "member_project_roles": _assign_member_project_roles(group_data.get("members", [])),
            "project_title": project_title,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "active",
            "balance_score": group_data.get("balance_score", 0)
        }
        groups.append(group)
    
    _save_groups(groups)
    
    return jsonify({
        "success": True,
        "message": f"Successfully created {len(groups)} balanced groups",
        "groups": groups
    })


if __name__ == "__main__":
    app.run(debug=True)