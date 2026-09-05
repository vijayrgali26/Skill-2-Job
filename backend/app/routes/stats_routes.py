"""Public statistics API — accessible by all authenticated roles.

Provides placement statistics for the Stats page shown to
students, placement officers, and admins.
"""

from datetime import date
from collections import defaultdict

from flask import Blueprint, jsonify, request

from app import db
from app.models import User, StudentProfile, Company, JobRole, PlacementRecord
from app.utils.auth_decorator import jwt_required
from sqlalchemy import extract, func

stats_bp = Blueprint("stats", __name__, url_prefix="/api/stats")


@stats_bp.route("", methods=["GET"])
@jwt_required
def get_stats():
    """Return comprehensive placement statistics for all 3 roles.

    Query params:
        year (int): Filter by graduation/placement year (optional)

    Returns:
        200: JSON with overview, yearly_trend, branch_breakdown,
             company_breakdown, on_off_campus, top_roles, package_stats,
             placed_students list.
    """
    year_filter = request.args.get("year", type=int)

    # ── 1. Overview ──────────────────────────────────────────────────
    total_students = User.query.filter_by(role="student").count()
    placed_base = db.session.query(func.count(func.distinct(PlacementRecord.profile_id)))
    if year_filter:
        placed_base = placed_base.filter(
            extract("year", PlacementRecord.placement_date) == year_filter
        )
    placed_students = placed_base.scalar() or 0
    total_companies = Company.query.count()
    placement_pct = round(placed_students / total_students * 100, 1) if total_students else 0

    avg_pkg_q = db.session.query(func.avg(PlacementRecord.package_lpa))
    max_pkg_q = db.session.query(func.max(PlacementRecord.package_lpa))
    if year_filter:
        avg_pkg_q = avg_pkg_q.filter(extract("year", PlacementRecord.placement_date) == year_filter)
        max_pkg_q = max_pkg_q.filter(extract("year", PlacementRecord.placement_date) == year_filter)
    avg_pkg = avg_pkg_q.scalar()
    max_pkg = max_pkg_q.scalar()

    # ── 2. Yearly trend (2021-2025) ───────────────────────────────────
    yearly = []
    for yr in [2021, 2022, 2023, 2024, 2025]:
        cnt = db.session.query(func.count(PlacementRecord.id)).filter(
            extract("year", PlacementRecord.placement_date) == yr
        ).scalar() or 0
        # Total students that graduated that year
        total_yr = StudentProfile.query.filter_by(graduation_year=yr).count()
        rate = round(cnt / total_yr * 100, 1) if total_yr else 0
        avg_yr = db.session.query(func.avg(PlacementRecord.package_lpa)).filter(
            extract("year", PlacementRecord.placement_date) == yr
        ).scalar()
        yearly.append({
            "year": yr,
            "placed": cnt,
            "total": total_yr,
            "rate": rate,
            "avg_package": round(float(avg_yr), 1) if avg_yr else 0,
        })

    # ── 3. Branch breakdown ──────────────────────────────────────────
    branch_q = (
        db.session.query(
            PlacementRecord.department,
            func.count(PlacementRecord.id).label("placed"),
        )
        .group_by(PlacementRecord.department)
    )
    if year_filter:
        branch_q = branch_q.filter(
            extract("year", PlacementRecord.placement_date) == year_filter
        )
    branch_rows = branch_q.all()

    # Get totals per branch
    branch_totals = dict(
        db.session.query(StudentProfile.branch, func.count(StudentProfile.id))
        .group_by(StudentProfile.branch)
        .all()
    )

    branch_breakdown = []
    for row in sorted(branch_rows, key=lambda r: r.placed, reverse=True):
        dept = row.department or "Unknown"
        total_b = branch_totals.get(dept, row.placed)
        branch_breakdown.append({
            "branch": dept,
            "placed": row.placed,
            "total": total_b,
            "rate": round(row.placed / total_b * 100, 1) if total_b else 0,
        })

    # ── 4. Company breakdown (top 15) ────────────────────────────────
    company_q = (
        db.session.query(
            Company.name,
            Company.industry,
            func.count(PlacementRecord.id).label("count"),
            func.avg(PlacementRecord.package_lpa).label("avg_pkg"),
        )
        .join(PlacementRecord, PlacementRecord.company_id == Company.id)
    )
    if year_filter:
        company_q = company_q.filter(
            extract("year", PlacementRecord.placement_date) == year_filter
        )
    company_q = (
        company_q
        .group_by(Company.id, Company.name, Company.industry)
        .order_by(func.count(PlacementRecord.id).desc())
        .limit(15)
    )
    company_breakdown = [
        {
            "company": r.name,
            "industry": r.industry or "—",
            "count": r.count,
            "avg_package": round(float(r.avg_pkg), 1) if r.avg_pkg else 0,
        }
        for r in company_q.all()
    ]

    # ── 5. On-campus vs Off-campus ───────────────────────────────────
    campus_q = (
        db.session.query(PlacementRecord.notes, func.count(PlacementRecord.id))
        .group_by(PlacementRecord.notes)
    )
    if year_filter:
        campus_q = campus_q.filter(
            extract("year", PlacementRecord.placement_date) == year_filter
        )
    on_campus = off_campus = 0
    for note, cnt in campus_q.all():
        if note and "off" in note.lower():
            off_campus += cnt
        else:
            on_campus += cnt

    # ── 6. Top job roles ────────────────────────────────────────────
    role_q = (
        db.session.query(JobRole.title, func.count(PlacementRecord.id).label("count"))
        .join(PlacementRecord, PlacementRecord.job_role_id == JobRole.id)
    )
    if year_filter:
        role_q = role_q.filter(
            extract("year", PlacementRecord.placement_date) == year_filter
        )
    role_q = (
        role_q
        .group_by(JobRole.title)
        .order_by(func.count(PlacementRecord.id).desc())
        .limit(10)
    )
    top_roles = [{"role": r.title, "count": r.count} for r in role_q.all()]

    # ── 7. Package distribution ──────────────────────────────────────
    pkg_ranges = {"0-5 LPA": 0, "5-10 LPA": 0, "10-15 LPA": 0,
                  "15-20 LPA": 0, "20+ LPA": 0}
    pkg_q = db.session.query(PlacementRecord.package_lpa).filter(
        PlacementRecord.package_lpa.isnot(None)
    )
    if year_filter:
        pkg_q = pkg_q.filter(extract("year", PlacementRecord.placement_date) == year_filter)
    for (pkg,) in pkg_q.all():
        if pkg < 5:       pkg_ranges["0-5 LPA"] += 1
        elif pkg < 10:    pkg_ranges["5-10 LPA"] += 1
        elif pkg < 15:    pkg_ranges["10-15 LPA"] += 1
        elif pkg < 20:    pkg_ranges["15-20 LPA"] += 1
        else:             pkg_ranges["20+ LPA"] += 1

    package_dist = [{"range": k, "count": v} for k, v in pkg_ranges.items()]

    # ── 8. Recent placed students list (last 50) ──────────────────────
    placed_list_q = (
        db.session.query(
            User.name,
            StudentProfile.branch,
            StudentProfile.cgpa,
            StudentProfile.graduation_year,
            Company.name.label("company"),
            JobRole.title.label("role"),
            PlacementRecord.package_lpa,
            PlacementRecord.notes,
            PlacementRecord.placement_date,
        )
        .join(StudentProfile, PlacementRecord.profile_id == StudentProfile.id)
        .join(User, StudentProfile.user_id == User.id)
        .join(Company, PlacementRecord.company_id == Company.id)
        .join(JobRole, PlacementRecord.job_role_id == JobRole.id)
    )
    if year_filter:
        placed_list_q = placed_list_q.filter(
            extract("year", PlacementRecord.placement_date) == year_filter
        )
    placed_list_q = placed_list_q.order_by(PlacementRecord.placement_date.desc()).limit(50)

    placed_students_list = [
        {
            "name": r.name,
            "branch": r.branch or "—",
            "cgpa": r.cgpa,
            "graduation_year": r.graduation_year,
            "company": r.company,
            "role": r.role,
            "package_lpa": r.package_lpa,
            "campus_type": "Off-Campus" if r.notes and "off" in r.notes.lower() else "On-Campus",
            "placement_date": r.placement_date.isoformat() if r.placement_date else None,
        }
        for r in placed_list_q.all()
    ]

    return jsonify({
        "overview": {
            "total_students": total_students,
            "placed_students": placed_students,
            "placement_percentage": placement_pct,
            "total_companies": total_companies,
            "avg_package": round(float(avg_pkg), 1) if avg_pkg else 0,
            "max_package": round(float(max_pkg), 1) if max_pkg else 0,
        },
        "yearly_trend": yearly,
        "branch_breakdown": branch_breakdown,
        "company_breakdown": company_breakdown,
        "on_off_campus": {"on_campus": on_campus, "off_campus": off_campus},
        "top_roles": top_roles,
        "package_distribution": package_dist,
        "placed_students": placed_students_list,
    }), 200
