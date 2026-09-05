"""Student profile service for the Skill2Job Placement System.

Provides CRUD operations for student profiles, including nested
project and certification management, field validation, and
skills storage.
"""

import json
import logging

from app import db
from app.models import StudentProfile, Project, Certification

logger = logging.getLogger(__name__)


def get_profile(user_id: int) -> dict | None:
    """Fetch a student profile with related projects and certifications.

    If the profile exists but has no ``skill_vector_json`` (e.g. because
    a previous SkillAnalyzer call failed), a retry is attempted here so
    the student sees up-to-date skill data.

    Args:
        user_id: The ID of the user whose profile to retrieve.

    Returns:
        Profile dict (via ``to_dict()``) or ``None`` if no profile exists.
    """
    profile = StudentProfile.query.filter_by(user_id=user_id).first()
    if profile is None:
        return None

    # Retry skill analysis if it was not completed previously
    if profile.skills_json and not profile.skill_vector_json:
        try:
            from app.services.skill_analyzer import SkillAnalyzer
            analyzer = SkillAnalyzer()
            analyzer.analyze_and_store(profile)
        except Exception:
            logger.exception(
                "SkillAnalyzer retry failed for user_id=%s on profile view",
                user_id,
            )

    return profile.to_dict()


def create_or_update_profile(user_id: int, data: dict) -> dict:
    """Validate and upsert a student profile with nested entries.

    Steps:
        1. Validate required fields: institution, degree, branch, cgpa.
        2. Validate CGPA is a float in [0.0, 10.0].
        3. Upsert the StudentProfile row.
        4. Store skills as JSON string in ``skills_json``.
        5. Replace existing projects and certifications with those in *data*.
        6. Commit and return ``profile.to_dict()``.

    Args:
        user_id: The owning user's ID.
        data: Dict with profile fields, optional ``skills``, ``projects``,
              and ``certifications`` lists.

    Returns:
        The saved profile as a dict.

    Raises:
        ValueError: When required fields are missing or CGPA is invalid.
    """
    # ---- 1. Validate required fields ----
    errors: dict[str, str] = {}
    for field in ("institution", "degree", "branch", "cgpa"):
        value = data.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            errors[field] = f"{field} is required"

    if errors:
        raise ValueError(errors)

    # ---- 2. Validate CGPA ----
    try:
        cgpa = float(data["cgpa"])
    except (TypeError, ValueError):
        raise ValueError({"cgpa": "CGPA must be a number"})

    if cgpa < 0.0 or cgpa > 10.0:
        raise ValueError({"cgpa": "CGPA must be between 0.0 and 10.0"})

    # ---- 3. Upsert profile ----
    profile = StudentProfile.query.filter_by(user_id=user_id).first()
    if profile is None:
        profile = StudentProfile(user_id=user_id)
        db.session.add(profile)

    profile.institution = data["institution"]
    profile.degree = data["degree"]
    profile.branch = data["branch"]
    profile.cgpa = cgpa
    profile.graduation_year = data.get("graduation_year")

    # ---- Handle dream_job (only update if key is present) ----
    if "dream_job" in data:
        dream_job = data["dream_job"]
        if dream_job is not None:
            dream_job = str(dream_job).strip()
            if len(dream_job) > 150:
                dream_job = dream_job[:150]
        profile.dream_job = dream_job

    # ---- Handle expected_lpa (only update if key is present) ----
    if "expected_lpa" in data:
        expected_lpa = data["expected_lpa"]
        if expected_lpa is not None:
            try:
                expected_lpa = float(expected_lpa)
            except (TypeError, ValueError):
                raise ValueError({"expected_lpa": "expected_lpa must be a number"})
            if expected_lpa < 0.0 or expected_lpa > 100.0:
                raise ValueError({"expected_lpa": "expected_lpa must be between 0.0 and 100.0"})
        profile.expected_lpa = expected_lpa

    if "preferred_company" in data:
        preferred_company = data["preferred_company"]
        profile.preferred_company = (
            str(preferred_company).strip()[:255]
            if preferred_company is not None and str(preferred_company).strip()
            else None
        )

    # ---- 4. Handle skills ----
    skills = data.get("skills")
    if skills is not None:
        profile.skills_json = json.dumps(skills)

    # ---- 5. Replace projects ----
    if "projects" in data:
        # Remove existing projects
        for proj in list(profile.projects):
            db.session.delete(proj)

        for proj_data in data["projects"]:
            project = Project(
                profile=profile,
                title=proj_data.get("title", ""),
                description=proj_data.get("description"),
                technologies=proj_data.get("technologies"),
            )
            db.session.add(project)

    # ---- 6. Replace certifications ----
    if "certifications" in data:
        for cert in list(profile.certifications):
            db.session.delete(cert)

        for cert_data in data["certifications"]:
            certification = Certification(
                profile=profile,
                name=cert_data.get("name", ""),
                issuer=cert_data.get("issuer"),
                issue_date=_parse_date(cert_data.get("issue_date")),
            )
            db.session.add(certification)

    # ---- 7. Commit ----
    db.session.commit()

    # ---- 8. Trigger skill analysis (graceful degradation) ----
    # If SkillAnalyzer fails, the profile is still saved; analysis will
    # be retried on the next profile view via ``get_profile``.
    try:
        from app.services.skill_analyzer import SkillAnalyzer
        analyzer = SkillAnalyzer()
        analyzer.analyze_and_store(profile)
    except Exception:
        logger.exception(
            "SkillAnalyzer failed for user_id=%s; profile saved without "
            "skill analysis — will retry on next profile view",
            user_id,
        )

    return profile.to_dict()


def add_project(profile_id: int, data: dict) -> dict:
    """Create a new project linked to an existing profile.

    Args:
        profile_id: The StudentProfile ID.
        data: Dict with ``title``, optional ``description`` and ``technologies``.

    Returns:
        The created project as a dict.

    Raises:
        ValueError: If the profile does not exist or title is missing.
    """
    profile = db.session.get(StudentProfile, profile_id)
    if profile is None:
        raise ValueError("Profile not found")

    title = data.get("title")
    if not title or not title.strip():
        raise ValueError({"title": "title is required"})

    project = Project(
        profile_id=profile_id,
        title=title,
        description=data.get("description"),
        technologies=data.get("technologies"),
    )
    db.session.add(project)
    db.session.commit()
    return project.to_dict()


def add_certification(profile_id: int, data: dict) -> dict:
    """Create a new certification linked to an existing profile.

    Args:
        profile_id: The StudentProfile ID.
        data: Dict with ``name``, optional ``issuer`` and ``issue_date``.

    Returns:
        The created certification as a dict.

    Raises:
        ValueError: If the profile does not exist or name is missing.
    """
    profile = db.session.get(StudentProfile, profile_id)
    if profile is None:
        raise ValueError("Profile not found")

    name = data.get("name")
    if not name or not name.strip():
        raise ValueError({"name": "name is required"})

    certification = Certification(
        profile_id=profile_id,
        name=name,
        issuer=data.get("issuer"),
        issue_date=_parse_date(data.get("issue_date")),
    )
    db.session.add(certification)
    db.session.commit()
    return certification.to_dict()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_date(value):
    """Parse an ISO-format date string, returning ``None`` on failure."""
    if value is None:
        return None
    from datetime import date as _date

    if isinstance(value, _date):
        return value
    try:
        return _date.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None
