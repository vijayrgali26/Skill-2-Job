"""Notification/Announcement API routes for the Skill2Job Placement System.

Provides endpoints for sending and listing notifications.
Accessible by placement officers and admins.
"""

from flask import Blueprint, g, jsonify, request

from app import db
from app.models import Notification, User, StudentProfile, PlacementRecord
from app.utils.auth_decorator import jwt_required, role_required

notification_bp = Blueprint("notifications", __name__, url_prefix="/api/notifications")


# ---------------------------------------------------------------------------
# List notifications
# ---------------------------------------------------------------------------

@notification_bp.route("", methods=["GET"])
@jwt_required
@role_required("placement_officer")
def list_notifications():
    """List all sent notifications for admin/officer view (most recent first)."""
    notifications = Notification.query.order_by(Notification.sent_at.desc()).limit(100).all()
    return jsonify([n.to_dict() for n in notifications]), 200


@notification_bp.route("/student", methods=["GET"])
@jwt_required
@role_required("student")
def list_student_notifications():
    """List notifications visible to the authenticated student.

    Returns notifications targeted at all_students, or shortlisted
    (if student is shortlisted), or their department.
    Most recent first, capped at 50.
    """
    from app.models import Shortlist, StudentProfile
    from sqlalchemy import or_

    user_id = g.current_user["user_id"]

    # Get student's profile for department check
    profile = StudentProfile.query.filter_by(user_id=user_id).first()
    branch = profile.branch.lower() if profile and profile.branch else None

    # Check if shortlisted
    is_shortlisted = False
    if profile:
        is_shortlisted = Shortlist.query.filter_by(profile_id=profile.id).first() is not None

    # Build query: show notifications for this student
    query = Notification.query

    conditions = [
        Notification.target_user_id == user_id,
        Notification.target_audience == "all_students",
    ]
    if is_shortlisted:
        conditions.append(Notification.target_audience == "shortlisted")
    if branch:
        conditions.append(
            (Notification.target_audience == "specific_department") &
            (db.func.lower(Notification.target_department) == branch)
        )

    from sqlalchemy import or_ as sql_or
    notifications = (
        query.filter(sql_or(*conditions))
        .order_by(Notification.sent_at.desc())
        .limit(50)
        .all()
    )
    return jsonify([n.to_dict() for n in notifications]), 200


# ---------------------------------------------------------------------------
# Send notification
# ---------------------------------------------------------------------------

@notification_bp.route("", methods=["POST"])
@jwt_required
@role_required("placement_officer")
def send_notification():
    """Send a notification/announcement.

    Accepts JSON body with:
        title (required): Notification title
        message (required): Notification body
        target_audience (optional): all_students | shortlisted | specific_department
        target_department (optional): Department name when target is specific_department
        send_email (optional): bool - whether to also send emails

    Returns:
        201: Created notification record with recipient count.
        400: Validation error.
    """
    json_data = request.get_json(silent=True)
    if not json_data:
        return jsonify({"error": {"code": "VALIDATION_ERROR", "message": "Request body must be valid JSON", "fields": {}}}), 400

    errors = {}
    title = json_data.get("title", "").strip() if json_data.get("title") else ""
    message = json_data.get("message", "").strip() if json_data.get("message") else ""

    if not title:
        errors["title"] = "Title is required"
    if not message:
        errors["message"] = "Message is required"

    if errors:
        return jsonify({"error": {"code": "VALIDATION_ERROR", "message": "Invalid input data", "fields": errors}}), 400

    target_audience = json_data.get("target_audience", "all_students")
    target_department = json_data.get("target_department")
    send_email = json_data.get("send_email", False)

    # Determine recipients
    recipients = _get_recipients(target_audience, target_department)
    recipient_count = len(recipients)

    notification = Notification(
        sent_by=g.current_user["user_id"],
        title=title,
        message=message,
        target_audience=target_audience,
        target_department=target_department,
        is_email=send_email,
        recipient_count=recipient_count,
    )
    db.session.add(notification)
    db.session.commit()

    # Send emails if requested
    if send_email and recipients:
        try:
            from app.services.email_service import get_email_service
            email_svc = get_email_service()
            for user in recipients:
                try:
                    email_svc.send_announcement(
                        to_email=user.email,
                        user_name=user.name,
                        title=title,
                        message=message,
                    )
                except Exception:
                    pass
        except Exception:
            pass

    return jsonify(notification.to_dict()), 201


# ---------------------------------------------------------------------------
# Delete notification
# ---------------------------------------------------------------------------

@notification_bp.route("/<int:id>", methods=["DELETE"])
@jwt_required
@role_required("placement_officer")
def delete_notification(id):
    """Delete a notification record.

    Returns:
        200: Confirmation message.
        404: Notification not found.
    """
    notification = db.session.get(Notification, id)
    if notification is None:
        return jsonify({"error": {"code": "NOT_FOUND", "message": "Notification not found", "fields": {}}}), 404

    db.session.delete(notification)
    db.session.commit()
    return jsonify({"message": "Notification deleted successfully"}), 200


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _get_recipients(target_audience: str, target_department: str | None) -> list:
    """Return list of User objects matching the target audience."""
    if target_audience == "all_students":
        return User.query.filter_by(role="student", status="active").all()

    if target_audience == "shortlisted":
        # Students who have at least one shortlist record
        from app.models import Shortlist
        shortlisted_profile_ids = db.session.query(Shortlist.profile_id).distinct().all()
        profile_ids = [r[0] for r in shortlisted_profile_ids]
        profiles = StudentProfile.query.filter(StudentProfile.id.in_(profile_ids)).all()
        user_ids = [p.user_id for p in profiles]
        return User.query.filter(User.id.in_(user_ids), User.status == "active").all()

    if target_audience == "specific_department" and target_department:
        # Students whose profile branch matches the department
        profiles = StudentProfile.query.filter(
            db.func.lower(StudentProfile.branch) == target_department.lower()
        ).all()
        user_ids = [p.user_id for p in profiles]
        return User.query.filter(User.id.in_(user_ids), User.status == "active").all()

    return []
