"""Job Matching Engine service for the Skill2Job Placement System.

Provides compatibility scoring via cosine similarity, job recommendations
ranked by match quality, skill gap identification, and candidate
shortlisting for placement officers.

Requirements: 6.1, 6.2, 6.3, 6.6, 7.1, 7.2, 7.3, 7.4, 10.1, 10.2, 10.3
"""

import json
import re

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from app import db
from app.models import (
    StudentProfile,
    JobRole,
    Company,
    User,
    SkillTaxonomy,
    CourseRecommendation,
)


class JobMatchingEngine:
    """Compute compatibility scores, recommend jobs, identify skill gaps,
    and shortlist candidates.

    All vector operations use scikit-learn's cosine similarity for
    consistency with the design specification.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compute_compatibility(
        self, skill_vector: np.ndarray, job_vector: np.ndarray
    ) -> float:
        """Compute cosine similarity between a student skill vector and a
        job requirement vector.

        Args:
            skill_vector: 1-D numpy array representing student skills.
            job_vector: 1-D numpy array representing job requirements.

        Returns:
            Float in [0.0, 1.0]. Returns 0.0 if either vector is all zeros.
        """
        # Guard against zero vectors (cosine similarity is undefined)
        if np.all(skill_vector == 0) or np.all(job_vector == 0):
            return 0.0

        # sklearn expects 2-D arrays
        score = cosine_similarity(
            skill_vector.reshape(1, -1),
            job_vector.reshape(1, -1),
        )[0][0]

        # Clamp to [0.0, 1.0] to handle floating-point edge cases
        return float(max(0.0, min(1.0, score)))

    def get_recommendations(
        self, student_id: int, limit: int = 20
    ) -> list[dict]:
        """Get ranked job recommendations for a student.

        Steps:
            1. Fetch the student profile and parse skill_vector_json.
            2. Fetch all active job roles with job_vector_json.
            3. Filter by eligibility (student CGPA >= job cgpa_threshold).
            4. Compute compatibility scores.
            5. Sort descending by score.
            6. Return top *limit* results.

        Args:
            student_id: The user_id of the student.
            limit: Maximum number of recommendations to return.

        Returns:
            List of dicts with keys: job_role_id, title, company_name,
            compatibility_score (percentage 0-100, 1 decimal), required_skills.
        """
        # 1. Get student profile
        profile = StudentProfile.query.filter_by(user_id=student_id).first()
        if not profile or not profile.skill_vector_json:
            return []

        student_vector_data = self._parse_vector_json(profile.skill_vector_json)
        if student_vector_data is None:
            return []

        student_vector = np.array(student_vector_data["vector"], dtype=float)
        student_cgpa = profile.cgpa or 0.0

        # 2. Get all active job roles
        job_roles = (
            JobRole.query
            .filter_by(is_active=True)
            .all()
        )

        if not job_roles:
            return []

        results: list[dict] = []

        for job in job_roles:
            # 3. Check eligibility: CGPA threshold
            threshold = job.cgpa_threshold or 0.0
            if student_cgpa < threshold:
                continue

            # Parse job vector
            if not job.job_vector_json:
                continue

            job_vector_data = self._parse_vector_json(job.job_vector_json)
            if job_vector_data is None:
                continue

            job_vector = np.array(job_vector_data["vector"], dtype=float)

            # 4. Compute compatibility score, giving the student's stated
            # career target a modest ranking boost when it is available.
            skill_score = self.compute_compatibility(student_vector, job_vector)
            title_score = self.compute_dream_job_title_match(
                profile.dream_job, job.title
            )
            score = (
                (skill_score * 0.8) + (title_score * 0.2)
                if profile.dream_job
                else skill_score
            )

            # Get company name
            company = db.session.get(Company, job.company_id)
            company_name = company.name if company else "Unknown"
            if profile.preferred_company and (
                profile.preferred_company.strip().lower() != company_name.strip().lower()
            ):
                continue
            if (
                profile.expected_lpa is not None
                and job.salary_lpa_min is not None
                and job.salary_lpa_min < profile.expected_lpa
            ):
                continue

            # Parse required skills
            required_skills = []
            if job.required_skills_json:
                try:
                    required_skills = json.loads(job.required_skills_json)
                except (json.JSONDecodeError, TypeError):
                    required_skills = []

            results.append({
                "job_role_id": job.id,
                "title": job.title,
                "company_name": company_name,
                "compatibility_score": round(score * 100, 1),
                "skill_compatibility_score": round(skill_score * 100, 1),
                "dream_job_match": round(title_score * 100, 1),
                "required_skills": required_skills,
            })

        # 5. Sort descending by score
        results.sort(key=lambda r: r["compatibility_score"], reverse=True)

        # 6. Return top N
        return results[:limit]

    def compute_dream_job_title_match(
        self, dream_job: str | None, job_title: str | None
    ) -> float:
        """Return a normalized token-overlap score for two role titles."""
        dream_tokens = self._role_tokens(dream_job)
        title_tokens = self._role_tokens(job_title)
        if not dream_tokens or not title_tokens:
            return 0.0
        return len(dream_tokens & title_tokens) / len(dream_tokens)

    def get_dream_job_progress(self, student_id: int) -> dict:
        """Summarize progress toward the student's selected dream job."""
        profile = StudentProfile.query.filter_by(user_id=student_id).first()
        if not profile or not profile.dream_job:
            return {
                "dream_job": None,
                "target_job": None,
                "match_score": 0,
                "matched_skills": 0,
                "required_skills": 0,
                "missing_skills": [],
                "recommended_courses": [],
            }

        student_data = self._parse_vector_json(profile.skill_vector_json)
        if student_data is None:
            return {
                "dream_job": profile.dream_job,
                "target_job": None,
                "match_score": 0,
                "matched_skills": 0,
                "required_skills": 0,
                "missing_skills": [],
                "recommended_courses": [],
            }

        student_vector = np.array(student_data["vector"], dtype=float)
        candidates = []
        for job in JobRole.query.filter_by(is_active=True).all():
            job_data = self._parse_vector_json(job.job_vector_json)
            if job_data is None:
                continue
            job_vector = np.array(job_data["vector"], dtype=float)
            title_score = self.compute_dream_job_title_match(profile.dream_job, job.title)
            skill_score = self.compute_compatibility(student_vector, job_vector)
            candidates.append((title_score, skill_score, job))

        if not candidates:
            return {
                "dream_job": profile.dream_job,
                "target_job": None,
                "match_score": 0,
                "matched_skills": 0,
                "required_skills": 0,
                "missing_skills": [],
                "recommended_courses": [],
            }

        _, skill_score, job = max(
            candidates, key=lambda item: (item[0], item[1])
        )
        required_skills = self._parse_required_skills(job.required_skills_json)
        missing_skills = self._missing_required_skills(profile, required_skills)
        recommended_courses = []
        for skill in missing_skills:
            courses = CourseRecommendation.query.filter(
                db.func.lower(CourseRecommendation.skill_name) == skill.lower()
            ).limit(3).all()
            recommended_courses.append({
                "skill": skill,
                "courses": [course.to_dict() for course in courses],
            })
        return {
            "dream_job": profile.dream_job,
            "target_job": {"id": job.id, "title": job.title},
            "match_score": round(skill_score * 100, 1),
            "matched_skills": max(0, len(required_skills) - len(missing_skills)),
            "required_skills": len(required_skills),
            "missing_skills": missing_skills,
            "recommended_courses": recommended_courses,
        }

    @staticmethod
    def _role_tokens(value: str | None) -> set[str]:
        if not value:
            return set()
        ignored = {"a", "an", "the", "and", "for", "of", "role", "engineer", "developer"}
        return {
            token for token in re.findall(r"[a-z0-9]+", value.lower())
            if token not in ignored
        } or set(re.findall(r"[a-z0-9]+", value.lower()))

    @staticmethod
    def _parse_required_skills(raw_skills: str | None) -> list[str]:
        if not raw_skills:
            return []
        try:
            parsed = json.loads(raw_skills)
            return [str(skill) for skill in parsed if str(skill).strip()]
        except (json.JSONDecodeError, TypeError):
            return []

    def _missing_required_skills(
        self, profile: StudentProfile, required_skills: list[str]
    ) -> list[str]:
        student_skills = set()
        if profile.skills_json:
            try:
                student_skills = {
                    str(skill).strip().lower()
                    for skill in json.loads(profile.skills_json)
                    if str(skill).strip()
                }
            except (json.JSONDecodeError, TypeError):
                student_skills = set()
        return [
            skill for skill in required_skills
            if skill.strip().lower() not in student_skills
        ]

    def compute_skill_gap(
        self,
        skill_vector: np.ndarray,
        job_vector: np.ndarray,
        skill_index: dict[str, int],
    ) -> list[dict]:
        """Identify skills the student is missing for a job role.

        For each dimension where the job requires the skill (job_vector > 0)
        but the student lacks it (skill_vector == 0), compute a deficit score.

        Args:
            skill_vector: 1-D numpy array of student skills.
            job_vector: 1-D numpy array of job requirements.
            skill_index: Dict mapping skill names (lowercase) to vector indices.

        Returns:
            List of {"skill": name, "deficit_score": float} sorted by
            deficit_score descending. Empty list if no gaps.
        """
        # Build reverse index: index -> skill name
        idx_to_skill: dict[int, str] = {
            idx: name for name, idx in skill_index.items()
        }

        gaps: list[dict] = []

        for i in range(len(job_vector)):
            if job_vector[i] > 0 and skill_vector[i] == 0:
                deficit = float(job_vector[i] - skill_vector[i])
                # Clamp to [0.0, 1.0]
                deficit = max(0.0, min(1.0, deficit))

                skill_name = idx_to_skill.get(i, f"skill_{i}")
                gaps.append({
                    "skill": skill_name,
                    "deficit_score": deficit,
                })

        # Sort by deficit_score descending
        gaps.sort(key=lambda g: g["deficit_score"], reverse=True)

        return gaps

    def shortlist_candidates(self, job_role_id: int) -> list[dict]:
        """Filter and rank eligible students for a job role.

        Steps:
            1. Fetch the job role and its vector.
            2. Fetch all student profiles with skill vectors.
            3. Filter by eligibility (CGPA >= threshold).
            4. Compute compatibility scores.
            5. Sort descending.
            6. Return candidate list.

        Args:
            job_role_id: The ID of the job role.

        Returns:
            List of dicts with keys: profile_id, name, cgpa,
            compatibility_score (percentage), matched_skills, missing_skills.
        """
        # 1. Get job role
        job = db.session.get(JobRole, job_role_id)
        if not job or not job.job_vector_json:
            return []

        job_vector_data = self._parse_vector_json(job.job_vector_json)
        if job_vector_data is None:
            return []

        job_vector = np.array(job_vector_data["vector"], dtype=float)
        job_skill_index = job_vector_data.get("skill_index", {})
        threshold = job.cgpa_threshold or 0.0

        # Parse required skills for the job
        required_skills_list: list[str] = []
        if job.required_skills_json:
            try:
                required_skills_list = json.loads(job.required_skills_json)
            except (json.JSONDecodeError, TypeError):
                required_skills_list = []

        # Build a set of required skill names (lowercase) for matching
        required_skills_lower = {s.lower() for s in required_skills_list}

        # 2. Get all student profiles with skill vectors
        profiles = (
            StudentProfile.query
            .filter(StudentProfile.skill_vector_json.isnot(None))
            .all()
        )

        candidates: list[dict] = []

        for profile in profiles:
            # 3. Filter by CGPA eligibility
            student_cgpa = profile.cgpa or 0.0
            if student_cgpa < threshold:
                continue

            student_vector_data = self._parse_vector_json(profile.skill_vector_json)
            if student_vector_data is None:
                continue

            student_vector = np.array(student_vector_data["vector"], dtype=float)
            student_skill_index = student_vector_data.get("skill_index", {})

            # 4. Compute compatibility score
            score = self.compute_compatibility(student_vector, job_vector)

            # Determine matched and missing skills
            # Build set of student skills (those with vector value > 0)
            student_skills_lower: set[str] = set()
            for skill_name, idx in student_skill_index.items():
                if idx < len(student_vector) and student_vector[idx] > 0:
                    student_skills_lower.add(skill_name.lower())

            matched = [s for s in required_skills_list if s.lower() in student_skills_lower]
            missing = [s for s in required_skills_list if s.lower() not in student_skills_lower]

            # Get student name from User
            user = db.session.get(User, profile.user_id)
            name = user.name if user else "Unknown"

            candidates.append({
                "profile_id": profile.id,
                "name": name,
                "cgpa": student_cgpa,
                "compatibility_score": round(score * 100, 1),
                "matched_skills": matched,
                "missing_skills": missing,
            })

        # 5. Sort descending by compatibility score
        candidates.sort(key=lambda c: c["compatibility_score"], reverse=True)

        return candidates

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _parse_vector_json(self, vector_json: str) -> dict | None:
        """Parse a skill_vector_json or job_vector_json string.

        Expected format::

            {
                "vector": [0.0, 1.0, ...],
                "skill_index": {"python": 0, ...},
                "version": "1.0"
            }

        Returns:
            Parsed dict, or None if parsing fails.
        """
        try:
            data = json.loads(vector_json)
            if "vector" not in data:
                return None
            return data
        except (json.JSONDecodeError, TypeError):
            return None
