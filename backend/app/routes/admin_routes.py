"""Admin and Placement Officer API routes for the Skill2Job Placement System.

Provides endpoints for company management, job role management,
candidate shortlisting, analytics, user management, skill taxonomy
management, and course recommendation management.

Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 10.1, 10.2, 10.3, 10.4, 10.5,
              11.1, 11.2, 11.3, 11.4, 11.5, 12.1, 12.2, 12.4, 12.5,
              13.1, 13.2, 13.3, 13.4, 8.4
"""

import json
from datetime import date, datetime

import bcrypt
from flask import Blueprint, request, jsonify

from app import db
from app.models import (
    Company,
    JobRole,
    Shortlist,
    StudentProfile,
    User,
    SkillTaxonomy,
    UncategorizedSkill,
    CourseRecommendation,
    PlacementRecord,
)
from app.services.skill_analyzer import SkillAnalyzer
from app.services.job_matching import JobMatchingEngine
from app.services.analytics_service import AnalyticsService
from app.utils.auth_decorator import jwt_required, role_required

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


# ---------------------------------------------------------------------------
# Company routes
# ---------------------------------------------------------------------------


@admin_bp.route("/companies", methods=["GET"])
@jwt_required
@role_required("placement_officer")
def list_companies():
    """List all companies.

    Returns:
        200: JSON list of all company records.

    Requirements: 9.1
    """
    companies = Company.query.all()
    return jsonify([c.to_dict() for c in companies]), 200


@admin_bp.route("/companies", methods=["POST"])
@jwt_required
@role_required("placement_officer")
def create_company():
    """Create a new company record.

    Accepts JSON body with name (required), industry, location,
    contact_email, contact_phone.

    Returns:
        201: Created company record.
        400: Validation error (missing company name).

    Requirements: 9.1, 9.6
    """
    json_data = request.get_json(silent=True)
    if not json_data:
        return (
            jsonify(
                {
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "Request body must be valid JSON",
                        "fields": {},
                    }
                }
            ),
            400,
        )

    name = json_data.get("name", "").strip() if json_data.get("name") else ""
    if not name:
        return (
            jsonify(
                {
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "Company name is required",
                        "fields": {"name": "Company name is required"},
                    }
                }
            ),
            400,
        )

    company = Company(
        name=name,
        industry=json_data.get("industry"),
        location=json_data.get("location"),
        contact_email=json_data.get("contact_email"),
        contact_phone=json_data.get("contact_phone"),
    )
    db.session.add(company)
    db.session.commit()

    return jsonify(company.to_dict()), 201


@admin_bp.route("/companies/<int:id>", methods=["PUT"])
@jwt_required
@role_required("placement_officer")
def update_company(id):
    """Update an existing company record.

    Accepts JSON body with any company fields to update.

    Returns:
        200: Updated company record.
        404: Company not found.

    Requirements: 9.4
    """
    company = db.session.get(Company, id)
    if company is None:
        return (
            jsonify(
                {
                    "error": {
                        "code": "NOT_FOUND",
                        "message": "Company not found",
                        "fields": {},
                    }
                }
            ),
            404,
        )

    json_data = request.get_json(silent=True)
    if not json_data:
        return (
            jsonify(
                {
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "Request body must be valid JSON",
                        "fields": {},
                    }
                }
            ),
            400,
        )

    if "name" in json_data:
        name = json_data["name"].strip() if json_data["name"] else ""
        if not name:
            return (
                jsonify(
                    {
                        "error": {
                            "code": "VALIDATION_ERROR",
                            "message": "Company name cannot be empty",
                            "fields": {"name": "Company name cannot be empty"},
                        }
                    }
                ),
                400,
            )
        company.name = name

    if "industry" in json_data:
        company.industry = json_data["industry"]
    if "location" in json_data:
        company.location = json_data["location"]
    if "contact_email" in json_data:
        company.contact_email = json_data["contact_email"]
    if "contact_phone" in json_data:
        company.contact_phone = json_data["contact_phone"]

    db.session.commit()

    return jsonify(company.to_dict()), 200


# ---------------------------------------------------------------------------
# Job Role routes
# ---------------------------------------------------------------------------


@admin_bp.route("/jobs", methods=["GET"])
@jwt_required
@role_required("placement_officer")
def list_jobs():
    """List all job roles with company info.

    Returns:
        200: JSON list of all job role records.
    """
    jobs = JobRole.query.order_by(JobRole.id.desc()).all()
    result = []
    for job in jobs:
        d = job.to_dict()
        company = db.session.get(Company, job.company_id)
        d["company_name"] = company.name if company else None
        result.append(d)
    return jsonify(result), 200


@admin_bp.route("/jobs", methods=["POST"])
@jwt_required
@role_required("placement_officer")
def create_job():
    """Create a new job role linked to a company.

    Accepts JSON body with company_id, title, description, required_skills
    (list), cgpa_threshold, academic_status.

    Generates a job requirement vector from the required skills using
    SkillAnalyzer and stores it as job_vector_json.

    Returns:
        201: Created job role record.
        400: Validation error.
        404: Company not found.

    Requirements: 9.2, 9.3
    """
    json_data = request.get_json(silent=True)
    if not json_data:
        return (
            jsonify(
                {
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "Request body must be valid JSON",
                        "fields": {},
                    }
                }
            ),
            400,
        )

    # Validate required fields
    errors = {}
    company_id = json_data.get("company_id")
    title = json_data.get("title", "").strip() if json_data.get("title") else ""

    if not company_id:
        errors["company_id"] = "Company ID is required"
    if not title:
        errors["title"] = "Job title is required"

    if errors:
        return (
            jsonify(
                {
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "Invalid input data",
                        "fields": errors,
                    }
                }
            ),
            400,
        )

    # Verify company exists
    company = db.session.get(Company, company_id)
    if company is None:
        return (
            jsonify(
                {
                    "error": {
                        "code": "NOT_FOUND",
                        "message": "Company not found",
                        "fields": {},
                    }
                }
            ),
            404,
        )

    required_skills = json_data.get("required_skills", [])

    # Generate job requirement vector
    job_vector_json = None
    if required_skills:
        try:
            analyzer = SkillAnalyzer()
            vector = analyzer.generate_job_requirement_vector(required_skills)
            # Build skill index
            from app.models import SkillTaxonomy
            taxonomy = (
                SkillTaxonomy.query
                .filter_by(is_deprecated=False)
                .order_by(SkillTaxonomy.id)
                .all()
            )
            skill_index = {
                skill.canonical_name.lower(): idx
                for idx, skill in enumerate(taxonomy)
            }
            vector_data = {
                "vector": vector.tolist(),
                "skill_index": skill_index,
                "version": "1.0",
            }
            job_vector_json = json.dumps(vector_data)
        except Exception:
            # If vector generation fails, proceed without it
            pass

    job_role = JobRole(
        company_id=company_id,
        title=title,
        description=json_data.get("description"),
        required_skills_json=json.dumps(required_skills) if required_skills else None,
        job_vector_json=job_vector_json,
        cgpa_threshold=json_data.get("cgpa_threshold", 0.0),
        salary_lpa_min=json_data.get("salary_lpa_min"),
        academic_status=json_data.get("academic_status"),
        is_active=True,
    )
    db.session.add(job_role)
    db.session.commit()
    _notify_matching_dream_job_students(job_role)

    return jsonify(job_role.to_dict()), 201


@admin_bp.route("/jobs/<int:id>", methods=["PUT"])
@jwt_required
@role_required("placement_officer")
def update_job(id):
    """Update an existing job role.

    If required_skills is changed, regenerates the job requirement vector.

    Returns:
        200: Updated job role record.
        404: Job role not found.

    Requirements: 9.4
    """
    job_role = db.session.get(JobRole, id)
    if job_role is None:
        return (
            jsonify(
                {
                    "error": {
                        "code": "NOT_FOUND",
                        "message": "Job role not found",
                        "fields": {},
                    }
                }
            ),
            404,
        )

    json_data = request.get_json(silent=True)
    if not json_data:
        return (
            jsonify(
                {
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "Request body must be valid JSON",
                        "fields": {},
                    }
                }
            ),
            400,
        )

    if "title" in json_data:
        title = json_data["title"].strip() if json_data["title"] else ""
        if not title:
            return (
                jsonify(
                    {
                        "error": {
                            "code": "VALIDATION_ERROR",
                            "message": "Job title cannot be empty",
                            "fields": {"title": "Job title cannot be empty"},
                        }
                    }
                ),
                400,
            )
        job_role.title = title

    if "description" in json_data:
        job_role.description = json_data["description"]
    if "cgpa_threshold" in json_data:
        job_role.cgpa_threshold = json_data["cgpa_threshold"]
    if "salary_lpa_min" in json_data:
        job_role.salary_lpa_min = json_data["salary_lpa_min"]
    if "academic_status" in json_data:
        job_role.academic_status = json_data["academic_status"]
    if "is_active" in json_data:
        job_role.is_active = json_data["is_active"]

    # Regenerate vector if skills changed
    skills_changed = False
    if "required_skills" in json_data:
        new_skills = json_data["required_skills"]
        old_skills = []
        if job_role.required_skills_json:
            try:
                old_skills = json.loads(job_role.required_skills_json)
            except (json.JSONDecodeError, TypeError):
                old_skills = []

        if sorted(new_skills) != sorted(old_skills):
            skills_changed = True

        job_role.required_skills_json = json.dumps(new_skills) if new_skills else None

        if skills_changed and new_skills:
            try:
                analyzer = SkillAnalyzer()
                vector = analyzer.generate_job_requirement_vector(new_skills)
                from app.models import SkillTaxonomy
                taxonomy = (
                    SkillTaxonomy.query
                    .filter_by(is_deprecated=False)
                    .order_by(SkillTaxonomy.id)
                    .all()
                )
                skill_index = {
                    skill.canonical_name.lower(): idx
                    for idx, skill in enumerate(taxonomy)
                }
                vector_data = {
                    "vector": vector.tolist(),
                    "skill_index": skill_index,
                    "version": "1.0",
                }
                job_role.job_vector_json = json.dumps(vector_data)
            except Exception:
                pass
        elif skills_changed and not new_skills:
            job_role.job_vector_json = None

    db.session.commit()
    _notify_matching_dream_job_students(job_role)

    return jsonify(job_role.to_dict()), 200


def _notify_matching_dream_job_students(job_role: JobRole) -> None:
    """Notify students whose optional career preferences match a live job."""
    if not job_role.is_active:
        return

    company = db.session.get(Company, job_role.company_id)
    if company is None:
        return

    profiles = StudentProfile.query.filter(
        StudentProfile.dream_job.isnot(None),
        StudentProfile.expected_lpa.isnot(None),
    ).all()
    for profile in profiles:
        title_match = JobMatchingEngine().compute_dream_job_title_match(
            profile.dream_job, job_role.title
        )
        company_match = (
            not profile.preferred_company
            or profile.preferred_company.strip().lower() == company.name.strip().lower()
        )
        package_match = (
            job_role.salary_lpa_min is None
            or job_role.salary_lpa_min >= profile.expected_lpa
        )
        if title_match <= 0 or not company_match or not package_match:
            continue
        message = (
            f"{company.name} is hiring for {job_role.title}. "
            "Review this opportunity in your job recommendations."
        )
        already_notified = Notification.query.filter_by(
            target_user_id=profile.user_id,
            title="Your dream job is hiring!",
            message=message,
        ).first()
        if already_notified:
            continue
        db.session.add(Notification(
            sent_by=g.current_user["user_id"],
            target_user_id=profile.user_id,
            title="Your dream job is hiring!",
            message=message,
            target_audience="individual",
            recipient_count=1,
        ))
    db.session.commit()


@admin_bp.route("/jobs/<int:id>", methods=["DELETE"])
@jwt_required
@role_required("placement_officer")
def delete_job(id):
    """Delete a job role from the database.

    Returns:
        200: Confirmation message.
        404: Job role not found.

    Requirements: 9.5
    """
    job_role = db.session.get(JobRole, id)
    if job_role is None:
        return (
            jsonify(
                {
                    "error": {
                        "code": "NOT_FOUND",
                        "message": "Job role not found",
                        "fields": {},
                    }
                }
            ),
            404,
        )

    db.session.delete(job_role)
    db.session.commit()

    return jsonify({"message": "Job role deleted successfully"}), 200


# ---------------------------------------------------------------------------
# Candidate Shortlisting routes
# ---------------------------------------------------------------------------


@admin_bp.route("/jobs/<int:id>/shortlist", methods=["GET"])
@jwt_required
@role_required("placement_officer")
def get_shortlist(id):
    """Get candidate shortlist for a job role.

    Calls JobMatchingEngine.shortlist_candidates() to filter and rank
    eligible students by compatibility score.

    Returns:
        200: JSON with sorted candidate list (name, CGPA, score,
             matched/missing skills) or message if no eligible candidates.
        404: Job role not found.

    Requirements: 10.1, 10.2, 10.3, 10.4
    """
    job_role = db.session.get(JobRole, id)
    if job_role is None:
        return (
            jsonify(
                {
                    "error": {
                        "code": "NOT_FOUND",
                        "message": "Job role not found",
                        "fields": {},
                    }
                }
            ),
            404,
        )

    engine = JobMatchingEngine()
    candidates = engine.shortlist_candidates(id)

    if not candidates:
        return jsonify({"message": "No eligible candidates found", "candidates": []}), 200

    return jsonify({"candidates": candidates}), 200


@admin_bp.route("/jobs/<int:id>/shortlist", methods=["POST"])
@jwt_required
@role_required("placement_officer")
def create_shortlist(id):
    """Mark selected candidates as shortlisted for a job role.

    Accepts a JSON body with a list of profile_ids. Creates Shortlist
    records for each with the compatibility score from the matching engine
    and status "Shortlisted".

    Returns:
        201: JSON with created shortlist records.
        400: Validation error (missing or empty profile_ids).
        404: Job role not found.

    Requirements: 10.5
    """
    job_role = db.session.get(JobRole, id)
    if job_role is None:
        return (
            jsonify(
                {
                    "error": {
                        "code": "NOT_FOUND",
                        "message": "Job role not found",
                        "fields": {},
                    }
                }
            ),
            404,
        )

    json_data = request.get_json(silent=True)
    if not json_data:
        return (
            jsonify(
                {
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "Request body must be valid JSON",
                        "fields": {},
                    }
                }
            ),
            400,
        )

    profile_ids = json_data.get("profile_ids", [])
    if not profile_ids:
        return (
            jsonify(
                {
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "profile_ids list is required and cannot be empty",
                        "fields": {"profile_ids": "profile_ids list is required and cannot be empty"},
                    }
                }
            ),
            400,
        )

    # Compute compatibility scores for all candidates to look up scores
    engine = JobMatchingEngine()
    candidates = engine.shortlist_candidates(id)
    score_map = {c["profile_id"]: c["compatibility_score"] for c in candidates}

    created_records = []
    for profile_id in profile_ids:
        # Verify the profile exists
        profile = db.session.get(StudentProfile, profile_id)
        if profile is None:
            continue

        # Avoid duplicate shortlist entries
        existing = Shortlist.query.filter_by(
            profile_id=profile_id, job_role_id=id
        ).first()
        if existing:
            continue

        compatibility_score = score_map.get(profile_id, 0.0)

        shortlist_record = Shortlist(
            profile_id=profile_id,
            job_role_id=id,
            compatibility_score=compatibility_score,
            status="Shortlisted",
        )
        db.session.add(shortlist_record)
        created_records.append(shortlist_record)

    db.session.commit()

    # Send email notifications to shortlisted students
    from app.services.email_service import get_email_service
    email_svc = get_email_service()
    for record in created_records:
        try:
            profile = db.session.get(StudentProfile, record.profile_id)
            if profile:
                user = db.session.get(User, profile.user_id)
                if user and user.email:
                    email_svc.send_shortlist_notification(
                        to_email=user.email,
                        user_name=user.name,
                        job_title=job_role.title,
                        company_name=db.session.get(Company, job_role.company_id).name if job_role.company_id else "Unknown",
                    )
        except Exception:
            pass  # Don't fail shortlisting if email fails

    return jsonify([r.to_dict() for r in created_records]), 201


# ---------------------------------------------------------------------------
# Analytics routes (Task 10.3)
# ---------------------------------------------------------------------------


@admin_bp.route("/analytics", methods=["GET"])
@jwt_required
@role_required("placement_officer")
def get_analytics():
    """Get placement analytics with optional date range filter.

    Query params:
        date_from (str): Optional start date (YYYY-MM-DD).
        date_to (str): Optional end date (YYYY-MM-DD).

    Returns:
        200: JSON with overview, department_breakdown, company_breakdown,
             and skill_demand.

    Requirements: 11.1, 11.2, 11.3, 11.4, 11.5
    """
    date_from = None
    date_to = None

    date_from_str = request.args.get("date_from")
    date_to_str = request.args.get("date_to")

    if date_from_str:
        try:
            date_from = date.fromisoformat(date_from_str)
        except ValueError:
            return (
                jsonify(
                    {
                        "error": {
                            "code": "VALIDATION_ERROR",
                            "message": "Invalid date_from format. Use YYYY-MM-DD.",
                            "fields": {"date_from": "Invalid date format"},
                        }
                    }
                ),
                400,
            )

    if date_to_str:
        try:
            date_to = date.fromisoformat(date_to_str)
        except ValueError:
            return (
                jsonify(
                    {
                        "error": {
                            "code": "VALIDATION_ERROR",
                            "message": "Invalid date_to format. Use YYYY-MM-DD.",
                            "fields": {"date_to": "Invalid date format"},
                        }
                    }
                ),
                400,
            )

    service = AnalyticsService()

    return jsonify(
        {
            "overview": service.get_overview_stats(),
            "department_breakdown": service.get_department_breakdown(date_from, date_to),
            "company_breakdown": service.get_company_breakdown(date_from, date_to),
            "skill_demand": service.get_skill_demand(),
        }
    ), 200


# ---------------------------------------------------------------------------
# User management routes (Task 10.4)
# ---------------------------------------------------------------------------


@admin_bp.route("/users", methods=["GET"])
@jwt_required
@role_required("admin")
def list_users():
    """List all users with pagination and optional search.

    Query params:
        page (int): Page number (default 1).
        per_page (int): Items per page (default 20).
        search (str): Optional search term for name or email.

    Returns:
        200: JSON with users list and pagination metadata.

    Requirements: 12.4, 12.5
    """
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    search = request.args.get("search", "").strip()

    query = User.query

    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            db.or_(
                User.name.ilike(search_filter),
                User.email.ilike(search_filter),
            )
        )

    query = query.order_by(User.id)
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify(
        {
            "users": [u.to_dict() for u in pagination.items],
            "total": pagination.total,
            "page": pagination.page,
            "per_page": pagination.per_page,
            "pages": pagination.pages,
        }
    ), 200


@admin_bp.route("/users", methods=["POST"])
@jwt_required
@role_required("admin")
def create_user():
    """Create a new user account with a specified role.

    Accepts JSON body with name, email, password, role, and optional phone.

    Returns:
        201: Created user record.
        400: Validation error.
        409: Email already exists.

    Requirements: 12.1
    """
    json_data = request.get_json(silent=True)
    if not json_data:
        return (
            jsonify(
                {
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "Request body must be valid JSON",
                        "fields": {},
                    }
                }
            ),
            400,
        )

    errors = {}
    name = json_data.get("name", "").strip() if json_data.get("name") else ""
    email = json_data.get("email", "").strip() if json_data.get("email") else ""
    password = json_data.get("password", "")
    role = json_data.get("role", "").strip() if json_data.get("role") else ""

    if not name:
        errors["name"] = "Name is required"
    if not email:
        errors["email"] = "Email is required"
    if not password:
        errors["password"] = "Password is required"
    elif len(password) < 8:
        errors["password"] = "Password must be at least 8 characters"
    if not role:
        errors["role"] = "Role is required"
    elif role not in ("student", "placement_officer", "admin"):
        errors["role"] = "Role must be student, placement_officer, or admin"

    if errors:
        return (
            jsonify(
                {
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "Invalid input data",
                        "fields": errors,
                    }
                }
            ),
            400,
        )

    # Check for duplicate email
    existing = User.query.filter_by(email=email).first()
    if existing:
        return (
            jsonify(
                {
                    "error": {
                        "code": "CONFLICT",
                        "message": "Email is already registered",
                        "fields": {"email": "Email is already registered"},
                    }
                }
            ),
            409,
        )

    password_hash = bcrypt.hashpw(
        password.encode("utf-8"), bcrypt.gensalt()
    ).decode("utf-8")

    user = User(
        name=name,
        email=email,
        phone=json_data.get("phone"),
        password_hash=password_hash,
        role=role,
        status="active",
    )
    db.session.add(user)
    db.session.commit()

    return jsonify(user.to_dict()), 201


@admin_bp.route("/users/<int:id>/status", methods=["PUT"])
@jwt_required
@role_required("admin")
def update_user_status(id):
    """Activate or deactivate a user account.

    Accepts JSON body with status ("active" or "inactive").

    Returns:
        200: Updated user record.
        400: Validation error.
        404: User not found.

    Requirements: 12.2
    """
    user = db.session.get(User, id)
    if user is None:
        return (
            jsonify(
                {
                    "error": {
                        "code": "NOT_FOUND",
                        "message": "User not found",
                        "fields": {},
                    }
                }
            ),
            404,
        )

    json_data = request.get_json(silent=True)
    if not json_data:
        return (
            jsonify(
                {
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "Request body must be valid JSON",
                        "fields": {},
                    }
                }
            ),
            400,
        )

    new_status = json_data.get("status", "").strip() if json_data.get("status") else ""
    if new_status not in ("active", "inactive"):
        return (
            jsonify(
                {
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "Status must be 'active' or 'inactive'",
                        "fields": {"status": "Status must be 'active' or 'inactive'"},
                    }
                }
            ),
            400,
        )

    user.status = new_status
    db.session.commit()

    return jsonify(user.to_dict()), 200


# ---------------------------------------------------------------------------
# Skill taxonomy management routes (Task 10.5)
# ---------------------------------------------------------------------------


@admin_bp.route("/skills/taxonomy", methods=["GET"])
@jwt_required
@role_required("admin")
def list_taxonomy():
    """Return the full skill taxonomy list.

    Returns:
        200: JSON list of all skill taxonomy entries.

    Requirements: 13.1
    """
    skills = SkillTaxonomy.query.order_by(SkillTaxonomy.id).all()
    return jsonify([s.to_dict() for s in skills]), 200


@admin_bp.route("/skills/taxonomy", methods=["POST"])
@jwt_required
@role_required("admin")
def create_taxonomy_skill():
    """Add a new skill to the taxonomy.

    Accepts JSON body with canonical_name (required), category, synonyms_json.

    Returns:
        201: Created skill taxonomy entry.
        400: Validation error.
        409: Skill already exists.

    Requirements: 13.1
    """
    json_data = request.get_json(silent=True)
    if not json_data:
        return (
            jsonify(
                {
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "Request body must be valid JSON",
                        "fields": {},
                    }
                }
            ),
            400,
        )

    canonical_name = (
        json_data.get("canonical_name", "").strip()
        if json_data.get("canonical_name")
        else ""
    )
    if not canonical_name:
        return (
            jsonify(
                {
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "Canonical name is required",
                        "fields": {"canonical_name": "Canonical name is required"},
                    }
                }
            ),
            400,
        )

    existing = SkillTaxonomy.query.filter_by(canonical_name=canonical_name).first()
    if existing:
        return (
            jsonify(
                {
                    "error": {
                        "code": "CONFLICT",
                        "message": "Skill already exists in taxonomy",
                        "fields": {"canonical_name": "Skill already exists"},
                    }
                }
            ),
            409,
        )

    synonyms = json_data.get("synonyms_json")
    if isinstance(synonyms, list):
        synonyms = json.dumps(synonyms)

    skill = SkillTaxonomy(
        canonical_name=canonical_name,
        category=json_data.get("category"),
        synonyms_json=synonyms,
        is_deprecated=False,
    )
    db.session.add(skill)
    db.session.commit()

    return jsonify(skill.to_dict()), 201


@admin_bp.route("/skills/taxonomy/<int:id>", methods=["PUT"])
@jwt_required
@role_required("admin")
def update_taxonomy_skill(id):
    """Update a skill taxonomy entry.

    Accepts JSON body with canonical_name, category, synonyms_json.

    Returns:
        200: Updated skill taxonomy entry.
        404: Skill not found.

    Requirements: 13.2
    """
    skill = db.session.get(SkillTaxonomy, id)
    if skill is None:
        return (
            jsonify(
                {
                    "error": {
                        "code": "NOT_FOUND",
                        "message": "Skill not found",
                        "fields": {},
                    }
                }
            ),
            404,
        )

    json_data = request.get_json(silent=True)
    if not json_data:
        return (
            jsonify(
                {
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "Request body must be valid JSON",
                        "fields": {},
                    }
                }
            ),
            400,
        )

    if "canonical_name" in json_data:
        new_name = json_data["canonical_name"].strip() if json_data["canonical_name"] else ""
        if not new_name:
            return (
                jsonify(
                    {
                        "error": {
                            "code": "VALIDATION_ERROR",
                            "message": "Canonical name cannot be empty",
                            "fields": {"canonical_name": "Canonical name cannot be empty"},
                        }
                    }
                ),
                400,
            )
        skill.canonical_name = new_name

    if "category" in json_data:
        skill.category = json_data["category"]

    if "synonyms_json" in json_data:
        synonyms = json_data["synonyms_json"]
        if isinstance(synonyms, list):
            synonyms = json.dumps(synonyms)
        skill.synonyms_json = synonyms

    db.session.commit()

    return jsonify(skill.to_dict()), 200


@admin_bp.route("/skills/taxonomy/<int:id>", methods=["DELETE"])
@jwt_required
@role_required("admin")
def delete_taxonomy_skill(id):
    """Soft-delete a skill by marking it as deprecated.

    Returns:
        200: Updated skill taxonomy entry with is_deprecated=True.
        404: Skill not found.

    Requirements: 13.3
    """
    skill = db.session.get(SkillTaxonomy, id)
    if skill is None:
        return (
            jsonify(
                {
                    "error": {
                        "code": "NOT_FOUND",
                        "message": "Skill not found",
                        "fields": {},
                    }
                }
            ),
            404,
        )

    skill.is_deprecated = True
    db.session.commit()

    return jsonify(skill.to_dict()), 200


@admin_bp.route("/skills/uncategorized", methods=["GET"])
@jwt_required
@role_required("admin")
def list_uncategorized_skills():
    """Return flagged uncategorized skills with occurrence counts.

    Returns:
        200: JSON list of uncategorized skill entries.

    Requirements: 13.4
    """
    skills = (
        UncategorizedSkill.query
        .filter_by(reviewed=False)
        .order_by(UncategorizedSkill.occurrence_count.desc())
        .all()
    )
    return jsonify([s.to_dict() for s in skills]), 200


# ---------------------------------------------------------------------------
# Course recommendation management route (Task 10.6)
# ---------------------------------------------------------------------------


@admin_bp.route("/courses", methods=["POST"])
@jwt_required
@role_required("placement_officer")
def create_course():
    """Add a new course recommendation.

    Accepts JSON body with skill_name (required), course_name (required),
    provider, url.

    Returns:
        201: Created course recommendation.
        400: Validation error.

    Requirements: 8.4
    """
    json_data = request.get_json(silent=True)
    if not json_data:
        return (
            jsonify(
                {
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "Request body must be valid JSON",
                        "fields": {},
                    }
                }
            ),
            400,
        )

    errors = {}
    skill_name = (
        json_data.get("skill_name", "").strip()
        if json_data.get("skill_name")
        else ""
    )
    course_name = (
        json_data.get("course_name", "").strip()
        if json_data.get("course_name")
        else ""
    )

    if not skill_name:
        errors["skill_name"] = "Skill name is required"
    if not course_name:
        errors["course_name"] = "Course name is required"

    if errors:
        return (
            jsonify(
                {
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "Invalid input data",
                        "fields": errors,
                    }
                }
            ),
            400,
        )

    course = CourseRecommendation(
        skill_name=skill_name,
        course_name=course_name,
        provider=json_data.get("provider"),
        url=json_data.get("url"),
    )
    db.session.add(course)
    db.session.commit()

    return jsonify(course.to_dict()), 201

# ---------------------------------------------------------------------------
# Placement Prediction routes (Random Forest ML)
# ---------------------------------------------------------------------------


@admin_bp.route("/predictions/train", methods=["POST"])
@jwt_required
@role_required("placement_officer")
def train_prediction_model():
    """Train the placement success prediction model.

    Uses Random Forest on historical placement data.

    Returns:
        200: Training stats (samples, accuracy, feature importances).
    """
    from app.services.placement_predictor import get_predictor

    predictor = get_predictor()
    result = predictor.train()
    return jsonify(result), 200


@admin_bp.route("/predictions/student/<int:student_id>", methods=["GET"])
@jwt_required
@role_required("placement_officer")
def predict_student_placement(student_id):
    """Predict placement probability for a specific student.

    Returns:
        200: Probability (0-100), confidence level, contributing factors.
        404: Student not found.
    """
    from app.services.placement_predictor import get_predictor

    predictor = get_predictor()
    result = predictor.predict(student_id)

    if "error" in result:
        return (
            jsonify({"error": {"code": "NOT_FOUND", "message": result["error"]}}),
            404,
        )

    return jsonify(result), 200


@admin_bp.route("/predictions/batch", methods=["GET"])
@jwt_required
@role_required("placement_officer")
def predict_batch_placement():
    """Predict placement probability for all students (candidate ranking).

    Returns:
        200: List of students ranked by placement probability.
    """
    from app.services.placement_predictor import get_predictor

    predictor = get_predictor()
    results = predictor.predict_batch()
    return jsonify({"predictions": results}), 200
