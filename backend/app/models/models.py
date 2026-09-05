"""SQLAlchemy models for the Skill2Job Placement System.

Defines all database entities, relationships, indexes, and serialization
helpers used throughout the application.
"""

from datetime import datetime, date, timezone

from app import db


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

class User(db.Model):
    """Application user with role-based access (student, placement_officer, admin)."""

    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True)
    phone = db.Column(db.String(20), nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(30), nullable=False, default="student")
    status = db.Column(db.String(20), nullable=False, default="active")
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    profile = db.relationship("StudentProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        db.Index("idx_user_email", "email", unique=True),
    )

    def __repr__(self):
        return f"<User id={self.id} email={self.email!r} role={self.role!r}>"

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "role": self.role,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# ---------------------------------------------------------------------------
# StudentProfile
# ---------------------------------------------------------------------------

class StudentProfile(db.Model):
    """Academic and skill profile for a student user."""

    __tablename__ = "student_profile"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, unique=True)
    institution = db.Column(db.String(255), nullable=True)
    degree = db.Column(db.String(100), nullable=True)
    branch = db.Column(db.String(100), nullable=True)
    cgpa = db.Column(db.Float, nullable=True)
    graduation_year = db.Column(db.Integer, nullable=True)
    skills_json = db.Column(db.Text, nullable=True)
    skill_vector_json = db.Column(db.Text, nullable=True)
    dream_job = db.Column(db.String(150), nullable=True)
    expected_lpa = db.Column(db.Float, nullable=True)
    preferred_company = db.Column(db.String(255), nullable=True)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    user = db.relationship("User", back_populates="profile")
    projects = db.relationship("Project", back_populates="profile", cascade="all, delete-orphan")
    certifications = db.relationship("Certification", back_populates="profile", cascade="all, delete-orphan")
    shortlists = db.relationship("Shortlist", back_populates="profile", cascade="all, delete-orphan")
    placement_records = db.relationship("PlacementRecord", back_populates="profile", cascade="all, delete-orphan")
    resume_uploads = db.relationship("ResumeUpload", back_populates="profile", cascade="all, delete-orphan")

    __table_args__ = (
        db.Index("idx_profile_user_id", "user_id"),
    )

    def __repr__(self):
        return f"<StudentProfile id={self.id} user_id={self.user_id}>"

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "institution": self.institution,
            "degree": self.degree,
            "branch": self.branch,
            "cgpa": self.cgpa,
            "graduation_year": self.graduation_year,
            "skills_json": self.skills_json,
            "skill_vector_json": self.skill_vector_json,
            "dream_job": self.dream_job,
            "expected_lpa": self.expected_lpa,
            "preferred_company": self.preferred_company,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "projects": [p.to_dict() for p in self.projects],
            "certifications": [c.to_dict() for c in self.certifications],
        }


# ---------------------------------------------------------------------------
# Project
# ---------------------------------------------------------------------------

class Project(db.Model):
    """A project entry linked to a student profile."""

    __tablename__ = "project"

    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey("student_profile.id"), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    technologies = db.Column(db.String(500), nullable=True)

    # Relationships
    profile = db.relationship("StudentProfile", back_populates="projects")

    def __repr__(self):
        return f"<Project id={self.id} title={self.title!r}>"

    def to_dict(self):
        return {
            "id": self.id,
            "profile_id": self.profile_id,
            "title": self.title,
            "description": self.description,
            "technologies": self.technologies,
        }


# ---------------------------------------------------------------------------
# Certification
# ---------------------------------------------------------------------------

class Certification(db.Model):
    """A certification entry linked to a student profile."""

    __tablename__ = "certification"

    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey("student_profile.id"), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    issuer = db.Column(db.String(255), nullable=True)
    issue_date = db.Column(db.Date, nullable=True)

    # Relationships
    profile = db.relationship("StudentProfile", back_populates="certifications")

    def __repr__(self):
        return f"<Certification id={self.id} name={self.name!r}>"

    def to_dict(self):
        return {
            "id": self.id,
            "profile_id": self.profile_id,
            "name": self.name,
            "issuer": self.issuer,
            "issue_date": self.issue_date.isoformat() if self.issue_date else None,
        }


# ---------------------------------------------------------------------------
# Company
# ---------------------------------------------------------------------------

class Company(db.Model):
    """A company that offers job roles for placement."""

    __tablename__ = "company"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    industry = db.Column(db.String(150), nullable=True)
    location = db.Column(db.String(255), nullable=True)
    contact_email = db.Column(db.String(255), nullable=True)
    contact_phone = db.Column(db.String(20), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    # Relationships
    job_roles = db.relationship("JobRole", back_populates="company", cascade="all, delete-orphan")
    placement_records = db.relationship("PlacementRecord", back_populates="company", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Company id={self.id} name={self.name!r}>"

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "industry": self.industry,
            "location": self.location,
            "contact_email": self.contact_email,
            "contact_phone": self.contact_phone,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ---------------------------------------------------------------------------
# JobRole
# ---------------------------------------------------------------------------

class JobRole(db.Model):
    """A job role offered by a company with skill requirements and eligibility criteria."""

    __tablename__ = "job_role"

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("company.id"), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    required_skills_json = db.Column(db.Text, nullable=True)
    job_vector_json = db.Column(db.Text, nullable=True)
    cgpa_threshold = db.Column(db.Float, nullable=True, default=0.0)
    salary_lpa_min = db.Column(db.Float, nullable=True)
    academic_status = db.Column(db.String(50), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    # Relationships
    company = db.relationship("Company", back_populates="job_roles")
    shortlists = db.relationship("Shortlist", back_populates="job_role", cascade="all, delete-orphan")
    placement_records = db.relationship("PlacementRecord", back_populates="job_role", cascade="all, delete-orphan")

    __table_args__ = (
        db.Index("idx_job_company_id", "company_id"),
        db.Index("idx_job_active", "is_active"),
    )

    def __repr__(self):
        return f"<JobRole id={self.id} title={self.title!r} active={self.is_active}>"

    def to_dict(self):
        return {
            "id": self.id,
            "company_id": self.company_id,
            "title": self.title,
            "description": self.description,
            "required_skills_json": self.required_skills_json,
            "job_vector_json": self.job_vector_json,
            "cgpa_threshold": self.cgpa_threshold,
            "salary_lpa_min": self.salary_lpa_min,
            "academic_status": self.academic_status,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ---------------------------------------------------------------------------
# Shortlist
# ---------------------------------------------------------------------------

class Shortlist(db.Model):
    """A shortlisting record linking a student profile to a job role."""

    __tablename__ = "shortlist"

    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey("student_profile.id"), nullable=False)
    job_role_id = db.Column(db.Integer, db.ForeignKey("job_role.id"), nullable=False)
    compatibility_score = db.Column(db.Float, nullable=True)
    status = db.Column(db.String(30), nullable=False, default="pending")
    shortlisted_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    # Relationships
    profile = db.relationship("StudentProfile", back_populates="shortlists")
    job_role = db.relationship("JobRole", back_populates="shortlists")

    __table_args__ = (
        db.Index("idx_shortlist_job", "job_role_id"),
    )

    def __repr__(self):
        return f"<Shortlist id={self.id} profile_id={self.profile_id} job_role_id={self.job_role_id}>"

    def to_dict(self):
        return {
            "id": self.id,
            "profile_id": self.profile_id,
            "job_role_id": self.job_role_id,
            "compatibility_score": self.compatibility_score,
            "status": self.status,
            "shortlisted_at": self.shortlisted_at.isoformat() if self.shortlisted_at else None,
        }


# ---------------------------------------------------------------------------
# SkillTaxonomy
# ---------------------------------------------------------------------------

class SkillTaxonomy(db.Model):
    """Canonical skill entry with category and synonym mappings."""

    __tablename__ = "skill_taxonomy"

    id = db.Column(db.Integer, primary_key=True)
    canonical_name = db.Column(db.String(150), nullable=False, unique=True)
    category = db.Column(db.String(100), nullable=True)
    synonyms_json = db.Column(db.Text, nullable=True)
    is_deprecated = db.Column(db.Boolean, nullable=False, default=False)

    __table_args__ = (
        db.Index("idx_skill_canonical", "canonical_name", unique=True),
    )

    def __repr__(self):
        return f"<SkillTaxonomy id={self.id} canonical_name={self.canonical_name!r}>"

    def to_dict(self):
        return {
            "id": self.id,
            "canonical_name": self.canonical_name,
            "category": self.category,
            "synonyms_json": self.synonyms_json,
            "is_deprecated": self.is_deprecated,
        }


# ---------------------------------------------------------------------------
# UncategorizedSkill
# ---------------------------------------------------------------------------

class UncategorizedSkill(db.Model):
    """A skill term flagged by the Skill Analyzer for admin review."""

    __tablename__ = "uncategorized_skill"

    id = db.Column(db.Integer, primary_key=True)
    term = db.Column(db.String(255), nullable=False)
    occurrence_count = db.Column(db.Integer, nullable=False, default=1)
    reviewed = db.Column(db.Boolean, nullable=False, default=False)
    flagged_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<UncategorizedSkill id={self.id} term={self.term!r}>"

    def to_dict(self):
        return {
            "id": self.id,
            "term": self.term,
            "occurrence_count": self.occurrence_count,
            "reviewed": self.reviewed,
            "flagged_at": self.flagged_at.isoformat() if self.flagged_at else None,
        }


# ---------------------------------------------------------------------------
# CourseRecommendation
# ---------------------------------------------------------------------------

class CourseRecommendation(db.Model):
    """A course recommendation mapped to a specific skill."""

    __tablename__ = "course_recommendation"

    id = db.Column(db.Integer, primary_key=True)
    skill_name = db.Column(db.String(150), nullable=False)
    course_name = db.Column(db.String(255), nullable=False)
    provider = db.Column(db.String(150), nullable=True)
    url = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<CourseRecommendation id={self.id} skill={self.skill_name!r}>"

    def to_dict(self):
        return {
            "id": self.id,
            "skill_name": self.skill_name,
            "course_name": self.course_name,
            "provider": self.provider,
            "url": self.url,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ---------------------------------------------------------------------------
# PlacementRecord
# ---------------------------------------------------------------------------

class PlacementRecord(db.Model):
    """Records a student's placement at a company for a specific job role."""

    __tablename__ = "placement_record"

    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey("student_profile.id"), nullable=False)
    job_role_id = db.Column(db.Integer, db.ForeignKey("job_role.id"), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey("company.id"), nullable=False)
    placement_date = db.Column(db.Date, nullable=True)
    department = db.Column(db.String(150), nullable=True)
    package_lpa = db.Column(db.Float, nullable=True)
    offer_letter_url = db.Column(db.String(500), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    # Relationships
    profile = db.relationship("StudentProfile", back_populates="placement_records")
    job_role = db.relationship("JobRole", back_populates="placement_records")
    company = db.relationship("Company", back_populates="placement_records")

    __table_args__ = (
        db.Index("idx_placement_date", "placement_date"),
        db.Index("idx_placement_dept", "department"),
    )

    def __repr__(self):
        return f"<PlacementRecord id={self.id} profile_id={self.profile_id} company_id={self.company_id}>"

    def to_dict(self):
        # Enrich with student name, job title, company name for convenience
        student_name = None
        job_title = None
        company_name = None
        try:
            if self.profile and self.profile.user:
                student_name = self.profile.user.name
            if self.job_role:
                job_title = self.job_role.title
            if self.company:
                company_name = self.company.name
        except Exception:
            pass
        return {
            "id": self.id,
            "profile_id": self.profile_id,
            "job_role_id": self.job_role_id,
            "company_id": self.company_id,
            "placement_date": self.placement_date.isoformat() if self.placement_date else None,
            "department": self.department,
            "package_lpa": self.package_lpa,
            "offer_letter_url": self.offer_letter_url,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "student_name": student_name,
            "job_title": job_title,
            "company_name": company_name,
        }


# ---------------------------------------------------------------------------
# ResumeUpload
# ---------------------------------------------------------------------------

class ResumeUpload(db.Model):
    """Metadata for a resume file uploaded by a student."""

    __tablename__ = "resume_upload"

    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey("student_profile.id"), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False)
    content_type = db.Column(db.String(100), nullable=False)
    uploaded_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    profile = db.relationship("StudentProfile", back_populates="resume_uploads")

    def __repr__(self):
        return f"<ResumeUpload id={self.id} filename={self.original_filename!r}>"

    def to_dict(self):
        return {
            "id": self.id,
            "profile_id": self.profile_id,
            "original_filename": self.original_filename,
            "stored_filename": self.stored_filename,
            "content_type": self.content_type,
            "uploaded_at": self.uploaded_at.isoformat() if self.uploaded_at else None,
        }


# ---------------------------------------------------------------------------
# PasswordResetToken
# ---------------------------------------------------------------------------

class PasswordResetToken(db.Model):
    """Temporary password reset tokens for users."""

    __tablename__ = "password_reset_token"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    token_hash = db.Column(db.String(128), nullable=False, unique=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, nullable=False, default=False)

    user = db.relationship("User")

    __table_args__ = (
        db.Index("idx_password_reset_token_hash", "token_hash", unique=True),
    )

    def __repr__(self):
        return f"<PasswordResetToken id={self.id} user_id={self.user_id} used={self.used}>"

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "used": self.used,
        }


# ---------------------------------------------------------------------------
# Interview
# ---------------------------------------------------------------------------

class Interview(db.Model):
    """An interview slot scheduled for a shortlisted student."""

    __tablename__ = "interview"

    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey("student_profile.id"), nullable=False)
    job_role_id = db.Column(db.Integer, db.ForeignKey("job_role.id"), nullable=True)
    company_id = db.Column(db.Integer, db.ForeignKey("company.id"), nullable=True)
    scheduled_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    interview_date = db.Column(db.Date, nullable=False)
    interview_time = db.Column(db.String(20), nullable=True)
    mode = db.Column(db.String(30), nullable=True, default="in-person")  # in-person, online, phone
    venue_or_link = db.Column(db.String(500), nullable=True)
    status = db.Column(db.String(30), nullable=False, default="scheduled")  # scheduled, completed, cancelled, no-show
    feedback = db.Column(db.Text, nullable=True)
    result = db.Column(db.String(30), nullable=True)  # selected, rejected, on-hold
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    profile = db.relationship("StudentProfile")
    job_role = db.relationship("JobRole")
    company = db.relationship("Company")
    scheduler = db.relationship("User", foreign_keys=[scheduled_by])

    __table_args__ = (
        db.Index("idx_interview_profile", "profile_id"),
        db.Index("idx_interview_date", "interview_date"),
        db.Index("idx_interview_status", "status"),
    )

    def __repr__(self):
        return f"<Interview id={self.id} profile_id={self.profile_id} date={self.interview_date}>"

    def to_dict(self):
        student_name = None
        job_title = None
        company_name = None
        try:
            if self.profile and self.profile.user:
                student_name = self.profile.user.name
            if self.job_role:
                job_title = self.job_role.title
            if self.company:
                company_name = self.company.name
        except Exception:
            pass
        return {
            "id": self.id,
            "profile_id": self.profile_id,
            "job_role_id": self.job_role_id,
            "company_id": self.company_id,
            "scheduled_by": self.scheduled_by,
            "interview_date": self.interview_date.isoformat() if self.interview_date else None,
            "interview_time": self.interview_time,
            "mode": self.mode,
            "venue_or_link": self.venue_or_link,
            "status": self.status,
            "feedback": self.feedback,
            "result": self.result,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "student_name": student_name,
            "job_title": job_title,
            "company_name": company_name,
        }


# ---------------------------------------------------------------------------
# Notification
# ---------------------------------------------------------------------------

class Notification(db.Model):
    """A notification/announcement sent by admin or placement officer."""

    __tablename__ = "notification"

    id = db.Column(db.Integer, primary_key=True)
    sent_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    target_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    title = db.Column(db.String(255), nullable=False)
    message = db.Column(db.Text, nullable=False)
    target_audience = db.Column(db.String(50), nullable=False, default="all_students")
    # all_students | shortlisted | specific_department
    target_department = db.Column(db.String(150), nullable=True)
    is_email = db.Column(db.Boolean, nullable=False, default=False)
    recipient_count = db.Column(db.Integer, nullable=True, default=0)
    sent_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    sender = db.relationship("User", foreign_keys=[sent_by])

    __table_args__ = (
        db.Index("idx_notification_sent_at", "sent_at"),
    )

    def __repr__(self):
        return f"<Notification id={self.id} title={self.title!r}>"

    def to_dict(self):
        sender_name = None
        try:
            if self.sender:
                sender_name = self.sender.name
        except Exception:
            pass
        return {
            "id": self.id,
            "sent_by": self.sent_by,
            "target_user_id": self.target_user_id,
            "sender_name": sender_name,
            "title": self.title,
            "message": self.message,
            "target_audience": self.target_audience,
            "target_department": self.target_department,
            "is_email": self.is_email,
            "recipient_count": self.recipient_count,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
        }
