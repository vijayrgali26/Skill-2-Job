"""Resume generator — two professional, ATS-friendly templates.

Templates:
  classic      - Blue header, traditional layout          (no photo)
  sidebar      - Dark left sidebar + right content        (student photo)
"""

import json, logging, re
from datetime import date
from html import escape
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether, BaseDocTemplate, Frame, PageTemplate,
)
from reportlab.pdfgen import canvas as rl_canvas

from app import db
from app.models import StudentProfile, User

logger = logging.getLogger(__name__)
W, H = A4

PALETTES = {
    "classic":    {"p": "#1a237e", "a": "#3949ab", "m": "#4b5563", "sb": None},
    "sidebar":    {"p": "#1e293b", "a": "#3b82f6", "m": "#64748b", "sb": "#1e293b"},
}
VALID_TEMPLATES = list(PALETTES.keys())


class ResumeGenerator:
    REQUIRED_FIELDS = {"name": "name", "institution": "institution",
                       "degree": "degree", "branch": "branch", "skills_json": "skills"}

    def validate_profile(self, profile: dict) -> tuple:
        missing = []
        for fk, dn in self.REQUIRED_FIELDS.items():
            v = profile.get(fk)
            if fk == "skills_json":
                if not self._has_valid_skills(v):
                    missing.append(dn)
            else:
                if v is None or (isinstance(v, str) and not v.strip()):
                    missing.append(dn)
        return (len(missing) == 0, missing)

    def calculate_ats_score(self, profile: dict) -> int:
        """Return a transparent 0-100 ATS readiness score for generated content."""
        fields = ("name", "email", "phone", "institution", "degree", "branch")
        score = sum(1 for field in fields if str(profile.get(field) or "").strip()) * 8
        skills = self._parse_skills(profile.get("skills_json"))
        score += min(len(skills), 10) * 3
        score += min(len(profile.get("projects") or []), 3) * 8
        score += 8 if profile.get("dream_job") else 0
        score += 8 if profile.get("cgpa") else 0
        score += 8 if profile.get("graduation_year") else 0
        return max(0, min(100, int(score)))

    def generate_resume(self, student_id: int, template_id: str = "classic",
                        profile_override: dict = None,
                        extra_sections: dict = None,
                        photo_base64: str = None) -> bytes:
        """Generate a PDF resume.

        Args:
            student_id: User ID of the student.
            template_id: One of VALID_TEMPLATES.
            profile_override: Dict of field overrides for missing profile data.
            extra_sections: Dict with optional sections:
                {
                  "work_experience": [{"title","company","duration","description"}],
                  "languages": ["English","Kannada"],
                  "hobbies": ["Reading","Coding"],
                  "courses": [{"name","provider","year"}],
                  "objective": "Custom objective text",
                  "linkedin": "url", "github": "url", "website": "url"
                }
            photo_base64: Base64-encoded JPEG/PNG for photo templates.
        """
        profile = StudentProfile.query.filter_by(user_id=student_id).first()
        if profile is None:
            raise ValueError("Student profile not found")
        user = db.session.get(User, student_id)
        if user is None:
            raise ValueError("User not found")

        pd = profile.to_dict()
        pd["name"] = user.name
        pd["email"] = user.email
        pd["phone"] = user.phone

        if profile_override:
            for k, v in profile_override.items():
                if v:
                    pd[k] = v

        valid, missing = self.validate_profile(pd)
        if not valid:
            raise ValueError(f"Profile is missing required fields: {', '.join(missing)}")

        tid = template_id if template_id in VALID_TEMPLATES else "classic"
        ex = extra_sections or {}

        ai_content = None
        if profile.dream_job and profile.dream_job.strip():
            try:
                from app.services.ai_resume_service import AIResumeService
                ai_content = AIResumeService().generate_ai_content(profile, user)
            except Exception:
                pass

        # Use custom objective if provided
        if ex.get("objective"):
            if ai_content:
                ai_content.career_objective = ex["objective"]
            else:
                pd["_objective"] = ex["objective"]

        pal = PALETTES[tid]
        kwargs = dict(pd=pd, profile=profile, pal=pal, ai=ai_content,
                      ex=ex, photo_b64=photo_base64)

        if tid == "sidebar":
            return self._build_sidebar(**kwargs)
        return self._build_classic(**kwargs)

    def get_download_filename(self, name: str) -> str:
        safe = re.sub(r"[^A-Za-z0-9_-]+", "_", name.strip()).strip("_") or "Student"
        return f"Resume_{safe}_{date.today().isoformat()}.pdf"

    # ------------------------------------------------------------------
    # Template 1: CLASSIC (blue, traditional)
    # ------------------------------------------------------------------
    def _build_classic(self, pd, profile, pal, ai, ex=None, photo_b64=None):
        ex = ex or {}
        buf = BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4,
            topMargin=0.5*inch, bottomMargin=0.5*inch,
            leftMargin=0.75*inch, rightMargin=0.75*inch)
        P = colors.HexColor(pal["p"]); M = colors.HexColor(pal["m"])
        st = getSampleStyleSheet()
        title_s = ParagraphStyle("T", parent=st["Title"], fontSize=22, textColor=P, spaceAfter=2)
        sub_s   = ParagraphStyle("S", parent=st["Normal"], fontSize=10, textColor=M, spaceAfter=4)
        sec_s   = ParagraphStyle("H", parent=st["Heading2"], fontSize=12, textColor=P,
                                  spaceBefore=10, spaceAfter=3)
        body_s  = ParagraphStyle("B", parent=st["Normal"], fontSize=10, leading=14, spaceAfter=3)
        bul_s   = ParagraphStyle("BL", parent=body_s, leftIndent=12, firstLineIndent=-8)

        skills = self._parse_skills(pd.get("skills_json"))
        el = []
        el.append(Paragraph(self._t(pd.get("name","")), title_s))
        contact_parts = list(filter(None, [pd.get("email"), pd.get("phone"),
                                            ex.get("linkedin"), ex.get("github")]))
        el.append(Paragraph(self._t(" | ".join(contact_parts)), sub_s))
        el.append(Spacer(1,4))
        el.append(HRFlowable(width="100%", thickness=2, color=P))
        el.append(Spacer(1,6))

        obj = pd.get("_objective") or (ai.career_objective if ai else self._summary(pd, skills))
        el.append(Paragraph("Career Objective", sec_s))
        el.append(Paragraph(self._t(obj), body_s))
        el += self._education_section(pd, sec_s, body_s)
        el += self._work_exp_section(ex, sec_s, body_s, bul_s)
        el += self._skills_section(skills, ai, sec_s, body_s)
        el += self._projects_section(profile, ai, sec_s, body_s, bul_s)
        el += self._certs_section(profile, sec_s, body_s)
        el += self._courses_section(ex, sec_s, body_s)
        el += self._languages_section(ex, sec_s, body_s)
        el += self._hobbies_section(ex, sec_s, body_s)

        doc.build(el)
        return buf.getvalue()

    # ------------------------------------------------------------------
    # Template 2: MODERN (teal, bold headers)
    # ------------------------------------------------------------------
    def _build_modern(self, pd, profile, pal, ai, ex=None, photo_b64=None):
        ex = ex or {}
        buf = BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4,
            topMargin=0.5*inch, bottomMargin=0.5*inch,
            leftMargin=0.75*inch, rightMargin=0.75*inch)
        P = colors.HexColor(pal["p"]); M = colors.HexColor(pal["m"])
        st = getSampleStyleSheet()
        title_s = ParagraphStyle("T", parent=st["Title"], fontSize=24, textColor=P, spaceAfter=2)
        sub_s   = ParagraphStyle("S", parent=st["Normal"], fontSize=10, textColor=M)
        sec_s   = ParagraphStyle("H", parent=st["Heading2"], fontSize=11, textColor=colors.white,
                                  spaceBefore=10, spaceAfter=4, backColor=P,
                                  borderPadding=(4,6,4,6))
        body_s  = ParagraphStyle("B", parent=st["Normal"], fontSize=10, leading=14, spaceAfter=3)
        bul_s   = ParagraphStyle("BL", parent=body_s, leftIndent=12, firstLineIndent=-8)

        skills = self._parse_skills(pd.get("skills_json"))
        el = []
        header_data = [[
            Paragraph(self._t(pd.get("name","")), title_s),
            Paragraph(self._t(" | ".join(filter(None,[pd.get("email"),pd.get("phone")]))), sub_s)
        ]]
        ht = Table(header_data, colWidths=[3.5*inch, 3*inch])
        ht.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"MIDDLE"),("LINEBELOW",(0,0),(-1,0),2,P)]))
        el.append(ht); el.append(Spacer(1,8))

        obj = pd.get("_objective") or (ai.career_objective if ai else self._summary(pd, skills))
        el.append(Paragraph("  CAREER OBJECTIVE", sec_s))
        el.append(Spacer(1,4)); el.append(Paragraph(self._t(obj), body_s))
        el += self._education_section(pd, sec_s, body_s, header="  EDUCATION")
        el += self._work_exp_section(ex, sec_s, body_s, bul_s, header="  WORK EXPERIENCE")
        el += self._skills_section(skills, ai, sec_s, body_s, header="  TECHNICAL SKILLS")
        el += self._projects_section(profile, ai, sec_s, body_s, bul_s, header="  PROJECTS")
        el += self._certs_section(profile, sec_s, body_s, header="  CERTIFICATIONS")
        el += self._courses_section(ex, sec_s, body_s, header="  COURSES")
        el += self._languages_section(ex, sec_s, body_s, header="  LANGUAGES")
        el += self._hobbies_section(ex, sec_s, body_s, header="  HOBBIES & INTERESTS")

        doc.build(el)
        return buf.getvalue()

    # ------------------------------------------------------------------
    # Template 3: MINIMAL (black/white)
    # ------------------------------------------------------------------
    def _build_minimal(self, pd, profile, pal, ai, ex=None, photo_b64=None):
        ex = ex or {}
        buf = BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4,
            topMargin=0.6*inch, bottomMargin=0.6*inch,
            leftMargin=0.85*inch, rightMargin=0.85*inch)
        BLACK = colors.HexColor("#111827"); GREY = colors.HexColor("#6b7280")
        st = getSampleStyleSheet()
        title_s = ParagraphStyle("T", parent=st["Title"], fontSize=26, textColor=BLACK,
                                  spaceAfter=1, fontName="Helvetica-Bold")
        sub_s   = ParagraphStyle("S", parent=st["Normal"], fontSize=9, textColor=GREY,
                                  spaceAfter=8, fontName="Helvetica")
        sec_s   = ParagraphStyle("H", parent=st["Heading2"], fontSize=10, textColor=BLACK,
                                  spaceBefore=12, spaceAfter=2, fontName="Helvetica-Bold",
                                  textTransform="uppercase")
        body_s  = ParagraphStyle("B", parent=st["Normal"], fontSize=9.5, leading=14,
                                  spaceAfter=3, fontName="Helvetica", textColor=BLACK)
        bul_s   = ParagraphStyle("BL", parent=body_s, leftIndent=10, firstLineIndent=-8)

        skills = self._parse_skills(pd.get("skills_json"))
        el = []
        el.append(Paragraph(self._t(pd.get("name","")), title_s))
        el.append(Paragraph(self._t(" · ".join(filter(None,[pd.get("email"),pd.get("phone")]))), sub_s))
        el.append(HRFlowable(width="100%", thickness=0.5, color=BLACK)); el.append(Spacer(1,6))

        obj = pd.get("_objective") or (ai.career_objective if ai else self._summary(pd, skills))
        el.append(Paragraph("Summary", sec_s))
        el.append(HRFlowable(width="100%", thickness=0.5, color=GREY)); el.append(Spacer(1,3))
        el.append(Paragraph(self._t(obj), body_s))
        el += self._education_section(pd, sec_s, body_s, hr_color=GREY)
        el += self._work_exp_section(ex, sec_s, body_s, bul_s, hr_color=GREY)
        el += self._skills_section(skills, ai, sec_s, body_s, hr_color=GREY)
        el += self._projects_section(profile, ai, sec_s, body_s, bul_s, hr_color=GREY)
        el += self._certs_section(profile, sec_s, body_s, hr_color=GREY)
        el += self._courses_section(ex, sec_s, body_s, hr_color=GREY)
        el += self._languages_section(ex, sec_s, body_s, hr_color=GREY)
        el += self._hobbies_section(ex, sec_s, body_s, hr_color=GREY)

        doc.build(el)
        return buf.getvalue()

    # ------------------------------------------------------------------
    # Template 4: SIDEBAR (dark left panel + photo circle)
    # ------------------------------------------------------------------
    def _build_sidebar(self, pd, profile, pal, ai, ex=None, photo_b64=None):
        from reportlab.platypus import FrameBreak
        ex = ex or {}
        buf = BytesIO()
        P = colors.HexColor(pal["p"]); A = colors.HexColor(pal["a"])
        WHITE = colors.white
        st = getSampleStyleSheet()

        PAGE_MARGIN = 0.42 * inch
        SB_W = 2.05 * inch
        COLUMN_GAP = 0.22 * inch
        CONT_X = PAGE_MARGIN + SB_W + COLUMN_GAP
        CONT_W = W - CONT_X - PAGE_MARGIN

        def on_page(canvas, doc):
            canvas.setFillColor(P)
            canvas.rect(0, 0, PAGE_MARGIN + SB_W, H, fill=1, stroke=0)
            cx = (PAGE_MARGIN + SB_W) / 2
            cy = H - 0.85 * inch
            # Draw photo or initials circle
            if photo_b64:
                try:
                    import base64, tempfile, os as _os
                    raw = base64.b64decode(photo_b64.split(",")[-1])
                    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
                    tmp.write(raw); tmp.close()
                    canvas.saveState()
                    p = canvas.beginPath()
                    p.circle(cx, cy, 0.42 * inch)
                    canvas.clipPath(p, stroke=0)
                    canvas.drawImage(tmp.name, cx - 0.42*inch, cy - 0.42*inch,
                                     0.84*inch, 0.84*inch, preserveAspectRatio=True)
                    canvas.restoreState()
                    _os.unlink(tmp.name)
                except Exception:
                    canvas.setFillColor(A); canvas.circle(cx, cy, 0.42*inch, fill=1, stroke=0)
            else:
                canvas.setFillColor(A); canvas.circle(cx, cy, 0.42*inch, fill=1, stroke=0)
                canvas.setFillColor(WHITE); canvas.setFont("Helvetica-Bold", 15)
                initials = "".join(w[0].upper() for w in pd.get("name","?").split()[:2])
                canvas.drawCentredString(cx, cy - 6, initials)

        name_s  = ParagraphStyle("SBN", parent=st["Normal"], fontSize=13, textColor=WHITE,
                                  fontName="Helvetica-Bold", spaceAfter=2, leading=15)
        role_s  = ParagraphStyle("SBR", parent=st["Normal"], fontSize=8.5, textColor=A,
                                  fontName="Helvetica", spaceAfter=6)
        sbsec_s = ParagraphStyle("SBS", parent=st["Normal"], fontSize=8, textColor=A,
                                  fontName="Helvetica-Bold", spaceBefore=8, spaceAfter=2,
                                  textTransform="uppercase")
        sbody_s = ParagraphStyle("SBB", parent=st["Normal"], fontSize=8, textColor=WHITE,
                                  fontName="Helvetica", leading=12, spaceAfter=2)
        sec_s   = ParagraphStyle("H",  parent=st["Heading2"], fontSize=12,
                                  textColor=P, spaceBefore=10, spaceAfter=3)
        body_s  = ParagraphStyle("B",  parent=st["Normal"], fontSize=10, leading=14, spaceAfter=3)
        bul_s   = ParagraphStyle("BL", parent=body_s, leftIndent=12, firstLineIndent=-8)

        skills = self._parse_skills(pd.get("skills_json"))

        left = [Spacer(1, 1.05 * inch)]
        left.append(Paragraph(self._t(pd.get("name", "")), name_s))
        left.append(Paragraph(self._t(pd.get("branch", "") or "Student"), role_s))
        left.append(Paragraph("Contact", sbsec_s))
        for v in filter(None, [pd.get("email"), pd.get("phone"),
                                ex.get("linkedin"), ex.get("github")]):
            left.append(Paragraph(self._t(str(v)), sbody_s))
        left.append(Paragraph("Education", sbsec_s))
        for k in ["degree", "institution", "cgpa", "graduation_year"]:
            v = pd.get(k)
            if v: left.append(Paragraph(self._t(str(v)), sbody_s))
        left.append(Paragraph("Skills", sbsec_s))
        for sk in skills[:14]:
            left.append(Paragraph(f"• {self._t(sk)}", sbody_s))
        if ex.get("languages"):
            left.append(Paragraph("Languages", sbsec_s))
            for lang in ex["languages"]:
                left.append(Paragraph(f"• {self._t(lang)}", sbody_s))
        if ex.get("hobbies"):
            left.append(Paragraph("Hobbies", sbsec_s))
            left.append(Paragraph(self._t(", ".join(ex["hobbies"])), sbody_s))
        left.append(FrameBreak())

        right = []
        obj = pd.get("_objective") or (ai.career_objective if ai else self._summary(pd, skills))
        right.append(Paragraph("Career Objective", sec_s))
        right.append(HRFlowable(width="100%", thickness=1, color=P))
        right.append(Spacer(1, 4))
        right.append(Paragraph(self._t(obj), body_s))
        right += self._work_exp_section(ex, sec_s, body_s, bul_s)
        right += self._education_section(pd, sec_s, body_s)
        right += self._projects_section(profile, ai, sec_s, body_s, bul_s)
        right += self._certs_section(profile, sec_s, body_s)
        right += self._courses_section(ex, sec_s, body_s)

        left_frame  = Frame(PAGE_MARGIN, PAGE_MARGIN, SB_W, H-2*PAGE_MARGIN,
                            leftPadding=8, rightPadding=8, topPadding=6, bottomPadding=6, id="sidebar")
        right_frame = Frame(CONT_X, PAGE_MARGIN, CONT_W, H-2*PAGE_MARGIN,
                            leftPadding=0, rightPadding=0, topPadding=6, bottomPadding=6, id="content")
        tpl = PageTemplate(id="sidebar_tpl", frames=[left_frame, right_frame], onPage=on_page)
        doc = BaseDocTemplate(buf, pagesize=A4, pageTemplates=[tpl])
        doc.build(left + right)
        return buf.getvalue()

    # ------------------------------------------------------------------
    # Template 5: EXECUTIVE (purple banner + photo)
    # ------------------------------------------------------------------
    def _build_executive(self, pd, profile, pal, ai, ex=None, photo_b64=None):
        from reportlab.platypus import FrameBreak
        ex = ex or {}
        buf = BytesIO()
        P = colors.HexColor(pal["p"]); A = colors.HexColor(pal["a"])
        WHITE = colors.white
        BANNER_H = 1.3 * inch
        MARGIN = 0.65 * inch

        def on_page(canvas, doc):
            canvas.setFillColor(P)
            canvas.rect(0, H - BANNER_H, W, BANNER_H, fill=1, stroke=0)
            cx = W - 0.75 * inch; cy = H - BANNER_H / 2
            if photo_b64:
                try:
                    import base64, tempfile, os as _os
                    raw = base64.b64decode(photo_b64.split(",")[-1])
                    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
                    tmp.write(raw); tmp.close()
                    canvas.saveState()
                    p = canvas.beginPath(); p.circle(cx, cy, 0.42*inch)
                    canvas.clipPath(p, stroke=0)
                    canvas.drawImage(tmp.name, cx-0.42*inch, cy-0.42*inch,
                                     0.84*inch, 0.84*inch, preserveAspectRatio=True)
                    canvas.restoreState(); _os.unlink(tmp.name)
                except Exception:
                    canvas.setFillColor(A); canvas.circle(cx, cy, 0.42*inch, fill=1, stroke=0)
            else:
                canvas.setFillColor(A); canvas.circle(cx, cy, 0.42*inch, fill=1, stroke=0)
                canvas.setFillColor(WHITE); canvas.setFont("Helvetica-Bold", 15)
                initials = "".join(w[0].upper() for w in pd.get("name","?").split()[:2])
                canvas.drawCentredString(cx, cy - 6, initials)
            canvas.setFillColor(WHITE); canvas.setFont("Helvetica-Bold", 18)
            canvas.drawString(MARGIN, H - BANNER_H * 0.42, pd.get("name", ""))
            canvas.setFont("Helvetica", 9); canvas.setFillColor(A)
            contact = " | ".join(filter(None, [pd.get("email"), pd.get("phone")]))
            canvas.drawString(MARGIN, H - BANNER_H * 0.65, contact)

        st = getSampleStyleSheet()
        sec_s  = ParagraphStyle("H",  parent=st["Heading2"], fontSize=12,
                                 textColor=P, spaceBefore=10, spaceAfter=3)
        body_s = ParagraphStyle("B",  parent=st["Normal"],  fontSize=10, leading=14, spaceAfter=3)
        bul_s  = ParagraphStyle("BL", parent=body_s, leftIndent=12, firstLineIndent=-8)

        skills = self._parse_skills(pd.get("skills_json"))
        obj = pd.get("_objective") or (ai.career_objective if ai else self._summary(pd, skills))
        el = [Spacer(1,8), HRFlowable(width="100%", thickness=2, color=P), Spacer(1,6)]
        el.append(Paragraph("Career Objective", sec_s))
        el.append(Paragraph(self._t(obj), body_s))
        el += self._education_section(pd, sec_s, body_s)
        el += self._work_exp_section(ex, sec_s, body_s, bul_s)
        el += self._skills_section(skills, ai, sec_s, body_s)
        el += self._projects_section(profile, ai, sec_s, body_s, bul_s)
        el += self._certs_section(profile, sec_s, body_s)
        el += self._courses_section(ex, sec_s, body_s)
        el += self._languages_section(ex, sec_s, body_s)
        el += self._hobbies_section(ex, sec_s, body_s)

        content_frame = Frame(MARGIN, 0.5*inch, W-2*MARGIN, H-BANNER_H-0.7*inch,
                              leftPadding=0, rightPadding=0, topPadding=4, bottomPadding=4, id="main")
        tpl = PageTemplate(id="exec_tpl", frames=[content_frame], onPage=on_page)
        doc = BaseDocTemplate(buf, pagesize=A4, pageTemplates=[tpl])
        doc.build(el)
        return buf.getvalue()

    # ------------------------------------------------------------------
    # Template 6: PHOTO_CARD (red card header + photo)
    # ------------------------------------------------------------------
    def _build_photo_card(self, pd, profile, pal, ai, ex=None, photo_b64=None):
        ex = ex or {}
        buf = BytesIO()
        P = colors.HexColor(pal["p"]); A = colors.HexColor(pal["a"])
        WHITE = colors.white
        CARD_H = 1.5 * inch
        MARGIN = 0.65 * inch

        def on_page(canvas, doc):
            canvas.setFillColor(P)
            canvas.rect(0, H - CARD_H, W, CARD_H, fill=1, stroke=0)
            canvas.setFillColor(A)
            canvas.rect(0, H - CARD_H - 4, W, 4, fill=1, stroke=0)
            cx = W - 1.0*inch; cy = H - CARD_H/2
            if photo_b64:
                try:
                    import base64, tempfile, os as _os
                    raw = base64.b64decode(photo_b64.split(",")[-1])
                    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
                    tmp.write(raw); tmp.close()
                    canvas.saveState()
                    p = canvas.beginPath(); p.circle(cx, cy, 0.48*inch)
                    canvas.clipPath(p, stroke=0)
                    canvas.drawImage(tmp.name, cx-0.48*inch, cy-0.48*inch,
                                     0.96*inch, 0.96*inch, preserveAspectRatio=True)
                    canvas.restoreState(); _os.unlink(tmp.name)
                except Exception:
                    canvas.setFillColor(WHITE); canvas.circle(cx, cy, 0.48*inch, fill=1, stroke=0)
            else:
                canvas.setFillColor(WHITE); canvas.circle(cx, cy, 0.48*inch, fill=1, stroke=0)
                canvas.setFillColor(P); canvas.setFont("Helvetica-Bold", 17)
                initials = "".join(w[0].upper() for w in pd.get("name","?").split()[:2])
                canvas.drawCentredString(cx, cy - 7, initials)
            canvas.setFillColor(WHITE); canvas.setFont("Helvetica-Bold", 17)
            canvas.drawString(MARGIN, H - CARD_H*0.38, pd.get("name",""))
            canvas.setFont("Helvetica", 9); canvas.setFillColor(colors.HexColor("#fecaca"))
            canvas.drawString(MARGIN, H - CARD_H*0.60, f"{pd.get('degree','')} | {pd.get('branch','')}")
            canvas.setFont("Helvetica", 8)
            contact = " | ".join(filter(None,[pd.get("email"),pd.get("phone")]))
            canvas.drawString(MARGIN, H - CARD_H*0.78, contact)

        st = getSampleStyleSheet()
        sec_s  = ParagraphStyle("H",  parent=st["Heading2"], fontSize=12,
                                 textColor=P, spaceBefore=10, spaceAfter=3)
        body_s = ParagraphStyle("B",  parent=st["Normal"],  fontSize=10, leading=14, spaceAfter=3)
        bul_s  = ParagraphStyle("BL", parent=body_s, leftIndent=12, firstLineIndent=-8)

        skills = self._parse_skills(pd.get("skills_json"))
        obj = pd.get("_objective") or (ai.career_objective if ai else self._summary(pd, skills))
        el = [Spacer(1,8), HRFlowable(width="100%", thickness=2, color=P), Spacer(1,6)]
        el.append(Paragraph("Career Objective", sec_s))
        el.append(Paragraph(self._t(obj), body_s))
        el += self._education_section(pd, sec_s, body_s)
        el += self._work_exp_section(ex, sec_s, body_s, bul_s)
        el += self._skills_section(skills, ai, sec_s, body_s)
        el += self._projects_section(profile, ai, sec_s, body_s, bul_s)
        el += self._certs_section(profile, sec_s, body_s)
        el += self._courses_section(ex, sec_s, body_s)
        el += self._languages_section(ex, sec_s, body_s)
        el += self._hobbies_section(ex, sec_s, body_s)

        content_frame = Frame(MARGIN, 0.5*inch, W-2*MARGIN, H-CARD_H-0.7*inch,
                              leftPadding=0, rightPadding=0, topPadding=4, bottomPadding=4, id="main")
        tpl = PageTemplate(id="card_tpl", frames=[content_frame], onPage=on_page)
        doc = BaseDocTemplate(buf, pagesize=A4, pageTemplates=[tpl])
        doc.build(el)
        return buf.getvalue()
        from reportlab.platypus import FrameBreak
        buf = BytesIO()
        P = colors.HexColor(pal["p"]); A = colors.HexColor(pal["a"])
        WHITE = colors.white
        st = getSampleStyleSheet()

        SB_W = 2.0 * inch
        MARGIN = 0.3 * inch
        CONT_X = SB_W + MARGIN + 8
        CONT_W = W - CONT_X - MARGIN

        def on_page(canvas, doc):
            canvas.setFillColor(P)
            canvas.rect(0, 0, SB_W + MARGIN, H, fill=1, stroke=0)
            cx = (SB_W + MARGIN) / 2
            cy = H - 0.85 * inch
            canvas.setFillColor(A)
            canvas.circle(cx, cy, 0.42 * inch, fill=1, stroke=0)
            canvas.setFillColor(WHITE)
            canvas.setFont("Helvetica-Bold", 15)
            initials = "".join(w[0].upper() for w in pd.get("name", "?").split()[:2])
            canvas.drawCentredString(cx, cy - 6, initials)

        name_s  = ParagraphStyle("SBN", parent=st["Normal"], fontSize=13, textColor=WHITE,
                                  fontName="Helvetica-Bold", spaceAfter=2, leading=15)
        role_s  = ParagraphStyle("SBR", parent=st["Normal"], fontSize=8.5, textColor=A,
                                  fontName="Helvetica", spaceAfter=6)
        sbsec_s = ParagraphStyle("SBS", parent=st["Normal"], fontSize=8, textColor=A,
                                  fontName="Helvetica-Bold", spaceBefore=8, spaceAfter=2,
                                  textTransform="uppercase")
        sbody_s = ParagraphStyle("SBB", parent=st["Normal"], fontSize=8, textColor=WHITE,
                                  fontName="Helvetica", leading=12, spaceAfter=2)
        sec_s   = ParagraphStyle("H",  parent=st["Heading2"], fontSize=12,
                                  textColor=P, spaceBefore=10, spaceAfter=3)
        body_s  = ParagraphStyle("B",  parent=st["Normal"], fontSize=10, leading=14, spaceAfter=3)
        bul_s   = ParagraphStyle("BL", parent=body_s, leftIndent=12, firstLineIndent=-8)

        skills = self._parse_skills(pd.get("skills_json"))

        # ── Sidebar (left frame) flowables ──
        left = [Spacer(1, 1.05 * inch)]
        left.append(Paragraph(self._t(pd.get("name", "")), name_s))
        left.append(Paragraph(self._t(pd.get("branch", "") or "Student"), role_s))
        left.append(Paragraph("Contact", sbsec_s))
        if pd.get("email"): left.append(Paragraph(self._t(pd["email"]), sbody_s))
        if pd.get("phone"): left.append(Paragraph(self._t(pd["phone"]), sbody_s))
        left.append(Paragraph("Education", sbsec_s))
        for k in ["degree", "institution", "cgpa", "graduation_year"]:
            v = pd.get(k)
            if v: left.append(Paragraph(self._t(str(v)), sbody_s))
        left.append(Paragraph("Skills", sbsec_s))
        for sk in skills[:14]:
            left.append(Paragraph(f"• {self._t(sk)}", sbody_s))
        left.append(FrameBreak())   # signals end of left frame → move to right

        # ── Main content (right frame) flowables ──
        right = []
        obj = ai.career_objective if ai else self._summary(pd, skills)
        right.append(Paragraph("Career Objective", sec_s))
        right.append(HRFlowable(width="100%", thickness=1, color=P))
        right.append(Spacer(1, 4))
        right.append(Paragraph(self._t(obj), body_s))
        right += self._education_section(pd, sec_s, body_s)
        right += self._projects_section(profile, ai, sec_s, body_s, bul_s)
        right += self._certs_section(profile, sec_s, body_s)

        # Two frames: left sidebar, right content
        left_frame  = Frame(MARGIN / 2, MARGIN, SB_W, H - 2 * MARGIN,
                            leftPadding=6, rightPadding=6, topPadding=4, bottomPadding=4,
                            id="sidebar")
        right_frame = Frame(CONT_X, MARGIN, CONT_W, H - 2 * MARGIN,
                            leftPadding=4, rightPadding=4, topPadding=4, bottomPadding=4,
                            id="content")

        tpl = PageTemplate(id="sidebar_tpl", frames=[left_frame, right_frame],
                           onPage=on_page)
        doc = BaseDocTemplate(buf, pagesize=A4, pageTemplates=[tpl])
        doc.build(left + right)
        return buf.getvalue()

    # ------------------------------------------------------------------
    # Template 5: EXECUTIVE (purple banner + photo)
    # ------------------------------------------------------------------
    def _build_executive(self, pd, profile, pal, ai):
        from reportlab.platypus import FrameBreak
        buf = BytesIO()
        P = colors.HexColor(pal["p"]); A = colors.HexColor(pal["a"])
        WHITE = colors.white
        BANNER_H = 1.3 * inch
        MARGIN = 0.65 * inch

        def on_page(canvas, doc):
            canvas.setFillColor(P)
            canvas.rect(0, H - BANNER_H, W, BANNER_H, fill=1, stroke=0)
            canvas.setFillColor(A)
            cx = W - 0.75 * inch; cy = H - BANNER_H / 2
            canvas.circle(cx, cy, 0.42 * inch, fill=1, stroke=0)
            canvas.setFillColor(WHITE)
            canvas.setFont("Helvetica-Bold", 15)
            initials = "".join(w[0].upper() for w in pd.get("name", "?").split()[:2])
            canvas.drawCentredString(cx, cy - 6, initials)
            # Name + contact drawn directly on canvas in banner
            canvas.setFillColor(WHITE)
            canvas.setFont("Helvetica-Bold", 18)
            canvas.drawString(MARGIN, H - BANNER_H * 0.42, pd.get("name", ""))
            canvas.setFont("Helvetica", 9)
            canvas.setFillColor(A)
            contact = " | ".join(filter(None, [pd.get("email"), pd.get("phone")]))
            canvas.drawString(MARGIN, H - BANNER_H * 0.65, contact)

        st = getSampleStyleSheet()
        sec_s  = ParagraphStyle("H",  parent=st["Heading2"], fontSize=12,
                                 textColor=P, spaceBefore=10, spaceAfter=3)
        body_s = ParagraphStyle("B",  parent=st["Normal"],  fontSize=10, leading=14, spaceAfter=3)
        bul_s  = ParagraphStyle("BL", parent=body_s, leftIndent=12, firstLineIndent=-8)

        skills = self._parse_skills(pd.get("skills_json"))
        obj = ai.career_objective if ai else self._summary(pd, skills)

        el = []
        el.append(Spacer(1, 8))
        el.append(HRFlowable(width="100%", thickness=2, color=P))
        el.append(Spacer(1, 6))
        el.append(Paragraph("Career Objective", sec_s))
        el.append(Paragraph(self._t(obj), body_s))
        el += self._education_section(pd, sec_s, body_s)
        el += self._skills_section(skills, ai, sec_s, body_s)
        el += self._projects_section(profile, ai, sec_s, body_s, bul_s)
        el += self._certs_section(profile, sec_s, body_s)

        content_frame = Frame(MARGIN, 0.5 * inch,
                              W - 2 * MARGIN, H - BANNER_H - 0.7 * inch,
                              leftPadding=0, rightPadding=0,
                              topPadding=4, bottomPadding=4, id="main")
        tpl = PageTemplate(id="exec_tpl", frames=[content_frame], onPage=on_page)
        doc = BaseDocTemplate(buf, pagesize=A4, pageTemplates=[tpl])
        doc.build(el)
        return buf.getvalue()

    # ------------------------------------------------------------------
    # Template 6: PHOTO_CARD (red card header + photo)
    # ------------------------------------------------------------------
    def _build_photo_card(self, pd, profile, pal, ai):
        buf = BytesIO()
        P = colors.HexColor(pal["p"]); A = colors.HexColor(pal["a"])
        WHITE = colors.white
        CARD_H = 1.5 * inch
        MARGIN = 0.65 * inch

        def on_page(canvas, doc):
            canvas.setFillColor(P)
            canvas.rect(0, H - CARD_H, W, CARD_H, fill=1, stroke=0)
            canvas.setFillColor(A)
            canvas.rect(0, H - CARD_H - 4, W, 4, fill=1, stroke=0)
            # Photo circle
            cx = W - 1.0 * inch; cy = H - CARD_H / 2
            canvas.setFillColor(WHITE)
            canvas.circle(cx, cy, 0.48 * inch, fill=1, stroke=0)
            canvas.setFillColor(P)
            canvas.setFont("Helvetica-Bold", 17)
            initials = "".join(w[0].upper() for w in pd.get("name", "?").split()[:2])
            canvas.drawCentredString(cx, cy - 7, initials)
            # Name + dept on card
            canvas.setFillColor(WHITE)
            canvas.setFont("Helvetica-Bold", 17)
            canvas.drawString(MARGIN, H - CARD_H * 0.38, pd.get("name", ""))
            canvas.setFont("Helvetica", 9)
            canvas.setFillColor(colors.HexColor("#fecaca"))
            dept = f"{pd.get('degree','')} | {pd.get('branch','')}"
            canvas.drawString(MARGIN, H - CARD_H * 0.60, dept)
            canvas.setFont("Helvetica", 8)
            contact = " | ".join(filter(None, [pd.get("email"), pd.get("phone")]))
            canvas.drawString(MARGIN, H - CARD_H * 0.78, contact)

        st = getSampleStyleSheet()
        sec_s  = ParagraphStyle("H",  parent=st["Heading2"], fontSize=12,
                                 textColor=P, spaceBefore=10, spaceAfter=3)
        body_s = ParagraphStyle("B",  parent=st["Normal"],  fontSize=10, leading=14, spaceAfter=3)
        bul_s  = ParagraphStyle("BL", parent=body_s, leftIndent=12, firstLineIndent=-8)

        skills = self._parse_skills(pd.get("skills_json"))
        obj = ai.career_objective if ai else self._summary(pd, skills)

        el = []
        el.append(Spacer(1, 8))
        el.append(HRFlowable(width="100%", thickness=2, color=P))
        el.append(Spacer(1, 6))
        el.append(Paragraph("Career Objective", sec_s))
        el.append(Paragraph(self._t(obj), body_s))
        el += self._education_section(pd, sec_s, body_s)
        el += self._skills_section(skills, ai, sec_s, body_s)
        el += self._projects_section(profile, ai, sec_s, body_s, bul_s)
        el += self._certs_section(profile, sec_s, body_s)

        content_frame = Frame(MARGIN, 0.5 * inch,
                              W - 2 * MARGIN, H - CARD_H - 0.7 * inch,
                              leftPadding=0, rightPadding=0,
                              topPadding=4, bottomPadding=4, id="main")
        tpl = PageTemplate(id="card_tpl", frames=[content_frame], onPage=on_page)
        doc = BaseDocTemplate(buf, pagesize=A4, pageTemplates=[tpl])
        doc.build(el)
        return buf.getvalue()

    # ------------------------------------------------------------------
    # Shared section builders
    # ------------------------------------------------------------------
    def _work_exp_section(self, ex, sec_s, body_s, bul_s,
                          header="Work Experience", hr_color=None):
        items = ex.get("work_experience", [])
        if not items: return []
        el = [Paragraph(header, sec_s)]
        if hr_color:
            el.append(HRFlowable(width="100%", thickness=0.5, color=hr_color))
            el.append(Spacer(1,3))
        for w in items:
            block = []
            title_line = f"<b>{self._t(w.get('title',''))}</b>"
            if w.get("company"): title_line += f" — {self._t(w['company'])}"
            if w.get("duration"): title_line += f" <i>({self._t(w['duration'])})</i>"
            block.append(Paragraph(title_line, body_s))
            if w.get("description"):
                for pt in self._split_points(w["description"]):
                    block.append(Paragraph(f"- {self._t(pt)}", bul_s))
            block.append(Spacer(1,4))
            el.append(KeepTogether(block))
        return el

    def _courses_section(self, ex, sec_s, body_s,
                         header="Courses & Training", hr_color=None):
        items = ex.get("courses", [])
        if not items: return []
        el = [Paragraph(header, sec_s)]
        if hr_color:
            el.append(HRFlowable(width="100%", thickness=0.5, color=hr_color))
            el.append(Spacer(1,3))
        for c in items:
            txt = f"<b>{self._t(c.get('name',''))}</b>"
            if c.get("provider"): txt += f" — {self._t(c['provider'])}"
            if c.get("year"): txt += f" ({self._t(str(c['year']))})"
            el.append(Paragraph(txt, body_s))
            el.append(Spacer(1,2))
        return el

    def _languages_section(self, ex, sec_s, body_s,
                            header="Languages", hr_color=None):
        langs = ex.get("languages", [])
        if not langs: return []
        el = [Paragraph(header, sec_s)]
        if hr_color:
            el.append(HRFlowable(width="100%", thickness=0.5, color=hr_color))
            el.append(Spacer(1,3))
        el.append(Paragraph(self._t(" | ".join(langs)), body_s))
        return el

    def _hobbies_section(self, ex, sec_s, body_s,
                         header="Hobbies & Interests", hr_color=None):
        hobbies = ex.get("hobbies", [])
        if not hobbies: return []
        el = [Paragraph(header, sec_s)]
        if hr_color:
            el.append(HRFlowable(width="100%", thickness=0.5, color=hr_color))
            el.append(Spacer(1,3))
        el.append(Paragraph(self._t(" • ".join(hobbies)), body_s))
        return el

    def _education_section(self, pd, sec_s, body_s, header="Education", hr_color=None):
        el = [Paragraph(header, sec_s)]
        if hr_color:
            el.append(HRFlowable(width="100%", thickness=0.5, color=hr_color))
            el.append(Spacer(1,3))
        rows = []
        for label, key in [("Institution","institution"),("Degree","degree"),
                            ("Branch","branch"),("CGPA","cgpa"),
                            ("Graduation Year","graduation_year")]:
            v = pd.get(key)
            if v: rows.append([label, str(v)])
        if rows:
            t = Table(rows, colWidths=[1.7*inch, 4.5*inch])
            t.setStyle(TableStyle([
                ("FONTNAME",(0,0),(0,-1),"Helvetica-Bold"),
                ("FONTSIZE",(0,0),(-1,-1),10),
                ("BOTTOMPADDING",(0,0),(-1,-1),3),
                ("TOPPADDING",(0,0),(-1,-1),2),
            ]))
            el.append(t)
        return el

    def _skills_section(self, skills, ai, sec_s, body_s, header="Technical Skills", hr_color=None):
        el = [Paragraph(header, sec_s)]
        if hr_color:
            el.append(HRFlowable(width="100%", thickness=0.5, color=hr_color))
            el.append(Spacer(1,3))
        cats = ai.skill_categories if ai and ai.skill_categories else self._group_skills(skills)
        for label, lst in cats.items():
            el.append(Paragraph(
                f"<b>{self._t(label)}:</b> {self._t(', '.join(lst))}", body_s))
            for skill in lst:
                el.append(Paragraph(self._t(self._skill_sentence(skill, label)), body_s))
        return el

    @staticmethod
    def _skill_sentence(skill, category):
        """Turn a skill label into useful, searchable resume language."""
        return (
            f"Applied {skill} in {category.lower()} work to build reliable solutions, "
            "collaborate with stakeholders, and deliver measurable outcomes."
        )

    def _projects_section(self, profile, ai, sec_s, body_s, bul_s,
                          header="Projects", hr_color=None):
        projs = profile.projects or []
        if not projs: return []
        el = [Paragraph(header, sec_s)]
        if hr_color:
            el.append(HRFlowable(width="100%", thickness=0.5, color=hr_color))
            el.append(Spacer(1,3))
        proj_descs = {}
        if ai and ai.project_descriptions:
            for p in ai.project_descriptions:
                proj_descs[p.get("title","").lower()] = p
        for proj in projs:
            block = []
            title = f"<b>{self._t(proj.title)}</b>"
            if proj.technologies: title += f" <i>({self._t(proj.technologies)})</i>"
            block.append(Paragraph(title, body_s))
            desc = proj.description or ""
            ai_p = proj_descs.get(proj.title.lower(), {})
            if ai_p.get("description"): desc = ai_p["description"]
            for pt in self._split_points(desc):
                block.append(Paragraph(f"- {self._t(pt)}", bul_s))
            block.append(Spacer(1,4))
            el.append(KeepTogether(block))
        return el

    def _certs_section(self, profile, sec_s, body_s, header="Certifications", hr_color=None):
        certs = profile.certifications or []
        if not certs: return []
        el = [Paragraph(header, sec_s)]
        if hr_color:
            el.append(HRFlowable(width="100%", thickness=0.5, color=hr_color))
            el.append(Spacer(1,3))
        for c in certs:
            txt = f"<b>{self._t(c.name)}</b>"
            if c.issuer: txt += f" — {self._t(c.issuer)}"
            if c.issue_date: txt += f" ({c.issue_date.isoformat()})"
            el.append(Paragraph(txt, body_s))
            el.append(Spacer(1,2))
        return el

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _has_valid_skills(v):
        if v is None: return False
        if isinstance(v, list): return len(v) > 0
        if isinstance(v, str):
            try: return isinstance(json.loads(v), list) and len(json.loads(v)) > 0
            except: return False
        return False

    @staticmethod
    def _parse_skills(v):
        if v is None: return []
        if isinstance(v, list): return [str(s).strip() for s in v if str(s).strip()]
        try:
            p = json.loads(v)
            if isinstance(p, list): return [str(s).strip() for s in p if str(s).strip()]
        except: pass
        return []

    @staticmethod
    def _t(v): return escape(str(v or ""), quote=True)

    @staticmethod
    def _split_points(text):
        parts = re.split(r"(?:\r?\n|[.;]\s+)", str(text).strip())
        return [p.strip(" -") for p in parts if p.strip(" -")]

    @staticmethod
    def _summary(pd, skills):
        deg = pd.get("degree") or "student"
        br  = pd.get("branch") or "engineering"
        top = ", ".join(skills[:5]) if skills else "key technologies"
        return (f"{deg} candidate in {br} with hands-on experience in {top}. "
                "Seeking placement opportunities to apply technical skills and grow professionally.")

    @staticmethod
    def _group_skills(skills):
        cats = {
            "Programming":   {"python","java","javascript","typescript","c","c++","c#","php","kotlin","r","go"},
            "Web & Backend": {"react","flask","django","node","express","html","css","fastapi","vue","angular"},
            "Database":      {"mysql","postgresql","mongodb","sqlite","redis","oracle","sql"},
            "AI & Data":     {"machine learning","ml","ai","nlp","pandas","numpy","tensorflow","scikit-learn","deep learning"},
            "DevOps & Cloud":{"git","github","docker","linux","aws","azure","gcp","kubernetes","ci/cd"},
        }
        grouped = {}; others = []
        for sk in skills:
            n = sk.lower(); matched = None
            for label, kws in cats.items():
                if n in kws or any(k in n for k in kws):
                    matched = label; break
            (grouped.setdefault(matched, []) if matched else others).append(sk)
        if others: grouped["Other"] = others
        return grouped
