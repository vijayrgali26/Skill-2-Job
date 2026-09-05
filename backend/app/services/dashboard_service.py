"""Dashboard service for the Skill2Job Placement System.

Aggregates role-specific summary data for the Student, Coordinator,
and Admin dashboards. Composes data from existing services
(AnalyticsService, JobMatchingEngine, SkillAnalyzer) and direct
model queries.

Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 3.1, 4.1, 4.2, 5.1, 5.2, 5.3, 9.1, 9.2
"""

import json
from collections import Counter

from sqlalchemy import func

from app import db
from app.models import StudentProfile, JobRole, Company, Shortlist, User, SkillTaxonomy, UncategorizedSkill
from app.services.analytics_service import AnalyticsService
from app.services.skill_analyzer import SkillAnalyzer
from app.services.job_matching import JobMatchingEngine


class DashboardService:
    """Aggregate dashboard data for each user role."""

    def __init__(self):
        self.skill_analyzer = SkillAnalyzer()
        self.job_matching = JobMatchingEngine()
        self.analytics_service = AnalyticsService()

    # ------------------------------------------------------------------
    # Student dashboard
    # ------------------------------------------------------------------

    def get_student_summary(self, user_id: int) -> dict:
        """Aggregate student dashboard data.

        Returns a dict with profile_completeness, skill_count,
        skill_breakdown, matched_job_count, and top_recommendations.

        If the student has no profile, returns zeroed-out defaults.

        Args:
            user_id: The user ID of the student.

        Returns:
            Dict matching the StudentDashboardResponse schema.
        """
        profile = StudentProfile.query.filter_by(user_id=user_id).first()

        if not profile:
            return {
                "profile_completeness": 0,
                "skill_count": 0,
                "skill_breakdown": {},
                "matched_job_count": 0,
                "top_recommendations": [],
                "dream_job_progress": {
                    "dream_job": None,
                    "target_job": None,
                    "match_score": 0,
                    "matched_skills": 0,
                    "required_skills": 0,
                    "missing_skills": [],
                },
            }

        # --- Profile completeness ---
        profile_completeness = self._compute_profile_completeness(profile)

        # --- Skills ---
        skills = self._parse_skills(profile)
        skill_count = len(skills)
        skill_breakdown = self._compute_skill_breakdown(skills)

        # --- Matched job count ---
        matched_job_count = self._compute_matched_job_count(profile)

        # --- Top recommendations ---
        top_recommendations = self._get_top_recommendations(user_id)
        dream_job_progress = self.job_matching.get_dream_job_progress(user_id)

        return {
            "profile_completeness": profile_completeness,
            "skill_count": skill_count,
            "skill_breakdown": skill_breakdown,
            "matched_job_count": matched_job_count,
            "top_recommendations": top_recommendations,
            "dream_job_progress": dream_job_progress,
        }

    # ------------------------------------------------------------------
    # Private helpers – student
    # ------------------------------------------------------------------

    def _compute_profile_completeness(self, profile: StudentProfile) -> int:
        """Compute profile completeness as a percentage (0-100).

        Checks 8 fields:
        1. institution
        2. degree
        3. branch
        4. cgpa
        5. graduation_year
        6. skills_json
        7. has_projects (at least one project)
        8. has_certifications (at least one certification)

        Returns:
            Integer percentage rounded to nearest int.
        """
        filled = 0
        total = 8

        if profile.institution:
            filled += 1
        if profile.degree:
            filled += 1
        if profile.branch:
            filled += 1
        if profile.cgpa is not None:
            filled += 1
        if profile.graduation_year is not None:
            filled += 1
        if profile.skills_json:
            filled += 1
        if profile.projects and len(profile.projects) > 0:
            filled += 1
        if profile.certifications and len(profile.certifications) > 0:
            filled += 1

        return round(filled / total * 100)

    def _parse_skills(self, profile: StudentProfile) -> list[str]:
        """Parse skills from the profile's skills_json field.

        Returns:
            List of skill name strings, or empty list if not available.
        """
        if not profile.skills_json:
            return []
        try:
            skills = json.loads(profile.skills_json)
            if isinstance(skills, list):
                return [str(s).strip() for s in skills if str(s).strip()]
            return []
        except (json.JSONDecodeError, TypeError):
            return []

    def _compute_skill_breakdown(self, skills: list[str]) -> dict[str, int]:
        """Group skills by category and return category→count dict.

        Uses SkillAnalyzer.categorize_skills() to group by category.
        Falls back to a single 'Skills' bucket when taxonomy is empty
        or skills are not yet categorized.

        Args:
            skills: List of skill name strings.

        Returns:
            Dict mapping category name to count of skills in that category.
        """
        if not skills:
            return {}

        categorized = self.skill_analyzer.categorize_skills(skills)

        # If taxonomy lookup returned nothing, bucket everything under 'Skills'
        if not categorized:
            return {"Skills": len(skills)}

        result = {category: len(skill_list) for category, skill_list in categorized.items()}

        # Any skills not matched to a category go into 'Other'
        categorized_skills = {s for lst in categorized.values() for s in lst}
        uncategorized = [s for s in skills if s not in categorized_skills]
        if uncategorized:
            result["Other"] = len(uncategorized)

        return result

    def _compute_matched_job_count(self, profile: StudentProfile) -> int:
        """Count active job roles the student is eligible for.

        A job matches if:
        - is_active is True
        - job_vector_json is not null
        - student CGPA >= job's cgpa_threshold

        Args:
            profile: The student's profile.

        Returns:
            Integer count of matching jobs.
        """
        student_cgpa = profile.cgpa or 0.0

        matched_jobs = (
            JobRole.query
            .filter(
                JobRole.is_active == True,  # noqa: E712
                JobRole.job_vector_json.isnot(None),
            )
            .all()
        )

        count = 0
        for job in matched_jobs:
            threshold = job.cgpa_threshold or 0.0
            if student_cgpa >= threshold:
                count += 1

        return count

    def _get_top_recommendations(self, user_id: int) -> list[dict]:
        """Get top 3 job recommendations for the student.

        Delegates to JobMatchingEngine.get_recommendations() and
        returns a simplified list with job_role_id, title,
        company_name, and compatibility_score.

        Args:
            user_id: The user ID of the student.

        Returns:
            List of up to 3 recommendation dicts.
        """
        recommendations = self.job_matching.get_recommendations(user_id, limit=3)

        return [
            {
                "job_role_id": rec["job_role_id"],
                "title": rec["title"],
                "company_name": rec["company_name"],
                "compatibility_score": rec["compatibility_score"],
            }
            for rec in recommendations
        ]

    # ------------------------------------------------------------------
    # Coordinator dashboard
    # ------------------------------------------------------------------

    def get_coordinator_summary(self) -> dict:
        """Aggregate coordinator/placement officer dashboard data.

        Returns a dict with placement_overview, active_job_count,
        shortlisted_count, recent_shortlists, and top_skills_demand.

        Requirements: 4.1, 4.2, 5.1, 5.2, 5.3, 9.2

        Returns:
            Dict matching the CoordinatorDashboardResponse schema.
        """
        # --- Placement overview (delegates to AnalyticsService) ---
        placement_overview = self.analytics_service.get_overview_stats()

        # --- Active job count ---
        active_job_count = JobRole.query.filter(
            JobRole.is_active == True  # noqa: E712
        ).count()

        # --- Shortlisted count ---
        shortlisted_count = Shortlist.query.count()

        # --- Recent shortlists (5 most recent) ---
        recent_shortlists = self._get_recent_shortlists(limit=5)

        # --- Top skills demand ---
        top_skills_demand = self._compute_top_skills_demand(limit=5)

        return {
            "placement_overview": placement_overview,
            "active_job_count": active_job_count,
            "shortlisted_count": shortlisted_count,
            "recent_shortlists": recent_shortlists,
            "top_skills_demand": top_skills_demand,
        }

    # ------------------------------------------------------------------
    # Admin dashboard
    # ------------------------------------------------------------------

    def get_admin_summary(self) -> dict:
        """Aggregate admin dashboard data.

        Returns a dict with user_counts (by_role, by_status, total),
        taxonomy_health (total_skills, deprecated_skills, uncategorized_pending),
        and placement_overview.

        Requirements: 7.1, 7.2, 7.4, 9.3

        Returns:
            Dict matching the AdminDashboardResponse schema.
        """
        # --- User counts ---
        user_counts = self._compute_user_counts()

        # --- Taxonomy health ---
        taxonomy_health = self._compute_taxonomy_health()

        # --- Placement overview (delegates to AnalyticsService) ---
        placement_overview = self.analytics_service.get_overview_stats()

        return {
            "user_counts": user_counts,
            "taxonomy_health": taxonomy_health,
            "placement_overview": placement_overview,
        }

    # ------------------------------------------------------------------
    # Private helpers – admin
    # ------------------------------------------------------------------

    def _compute_user_counts(self) -> dict:
        """Compute user counts grouped by role and status.

        Returns:
            Dict with by_role, by_status, and total.
        """
        # Count by role
        role_results = (
            db.session.query(User.role, func.count(User.id))
            .group_by(User.role)
            .all()
        )
        by_role = {role: count for role, count in role_results}

        # Count by status
        status_results = (
            db.session.query(User.status, func.count(User.id))
            .group_by(User.status)
            .all()
        )
        by_status = {status: count for status, count in status_results}

        # Total
        total = User.query.count()

        return {
            "by_role": by_role,
            "by_status": by_status,
            "total": total,
        }

    def _compute_taxonomy_health(self) -> dict:
        """Compute taxonomy health metrics.

        Returns:
            Dict with total_skills (non-deprecated), deprecated_skills,
            and uncategorized_pending.
        """
        total_skills = SkillTaxonomy.query.filter(
            SkillTaxonomy.is_deprecated == False  # noqa: E712
        ).count()

        deprecated_skills = SkillTaxonomy.query.filter(
            SkillTaxonomy.is_deprecated == True  # noqa: E712
        ).count()

        uncategorized_pending = UncategorizedSkill.query.filter(
            UncategorizedSkill.reviewed == False  # noqa: E712
        ).count()

        return {
            "total_skills": total_skills,
            "deprecated_skills": deprecated_skills,
            "uncategorized_pending": uncategorized_pending,
        }

    # ------------------------------------------------------------------
    # Private helpers – coordinator
    # ------------------------------------------------------------------

    def _get_recent_shortlists(self, limit: int = 5) -> list[dict]:
        """Get the most recent shortlist records with joined data.

        Joins Shortlist with User (via StudentProfile), JobRole, and
        Company to return student_name, job_title, company_name,
        compatibility_score, and shortlisted_at.

        Args:
            limit: Maximum number of records to return.

        Returns:
            List of shortlist dicts sorted by shortlisted_at descending.
        """
        results = (
            db.session.query(
                User.name.label("student_name"),
                JobRole.title.label("job_title"),
                Company.name.label("company_name"),
                Shortlist.compatibility_score,
                Shortlist.shortlisted_at,
            )
            .join(StudentProfile, Shortlist.profile_id == StudentProfile.id)
            .join(User, StudentProfile.user_id == User.id)
            .join(JobRole, Shortlist.job_role_id == JobRole.id)
            .join(Company, JobRole.company_id == Company.id)
            .order_by(Shortlist.shortlisted_at.desc())
            .limit(limit)
            .all()
        )

        return [
            {
                "student_name": row.student_name,
                "job_title": row.job_title,
                "company_name": row.company_name,
                "compatibility_score": row.compatibility_score or 0.0,
                "shortlisted_at": (
                    row.shortlisted_at.isoformat()
                    if row.shortlisted_at
                    else None
                ),
            }
            for row in results
        ]

    def _compute_top_skills_demand(self, limit: int = 5) -> list[dict]:
        """Aggregate required skills from active job roles and return top N.

        Parses required_skills_json from each active JobRole, counts
        occurrences of each skill, and returns the top skills sorted
        by count descending.

        Args:
            limit: Maximum number of skills to return.

        Returns:
            List of dicts with skill and count, sorted by count descending.
        """
        active_jobs = JobRole.query.filter(
            JobRole.is_active == True  # noqa: E712
        ).all()

        skill_counter: Counter = Counter()
        for job in active_jobs:
            if not job.required_skills_json:
                continue
            try:
                skills = json.loads(job.required_skills_json)
            except (json.JSONDecodeError, TypeError):
                continue
            if isinstance(skills, list):
                for skill in skills:
                    normalized = str(skill).strip()
                    if normalized:
                        skill_counter[normalized] += 1

        top_skills = skill_counter.most_common(limit)

        return [{"skill": name, "count": count} for name, count in top_skills]
