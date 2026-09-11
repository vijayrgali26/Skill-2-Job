"""
Seed 5 years of realistic placement statistics (2021-2025).
Creates students, profiles, placement records across branches and companies.

Run: python seed_stats.py
Safe to re-run (idempotent on users).
"""
import json, sys, os, random
from datetime import date, timedelta
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import bcrypt
from dotenv import load_dotenv

load_dotenv()

from app import create_app, db
from app.models import (
    User, StudentProfile, Project, Certification,
    Company, JobRole, PlacementRecord,
)

# ── Realistic ATMECE-style data ───────────────────────────────────────────────

BRANCHES = {
    "Computer Science":       {"total": 120, "place_rate": 0.82},
    "Information Science":    {"total": 60,  "place_rate": 0.74},
    "Electronics":            {"total": 90,  "place_rate": 0.65},
    "Mechanical":             {"total": 80,  "place_rate": 0.48},
    "Civil":                  {"total": 60,  "place_rate": 0.38},
    "Electrical":             {"total": 50,  "place_rate": 0.52},
}

COMPANIES_DATA = [
    ("Infosys",          "IT Services",       "Bangalore",  12.0,  False),
    ("Wipro",            "IT Services",       "Bangalore",  10.5,  False),
    ("TCS",              "IT Consulting",     "Chennai",    11.0,  False),
    ("Cognizant",        "IT Services",       "Hyderabad",  10.0,  False),
    ("Accenture",        "IT Consulting",     "Bangalore",  13.5,  False),
    ("HCL Technologies", "IT Services",       "Noida",      9.5,   False),
    ("Capgemini",        "IT Services",       "Pune",       10.0,  False),
    ("Tech Mahindra",    "IT Services",       "Hyderabad",  9.0,   False),
    ("Amazon",           "E-Commerce / Cloud","Bangalore",  25.0,  False),
    ("Flipkart",         "E-Commerce",        "Bangalore",  20.0,  False),
    ("Google",           "Technology",        "Hyderabad",  40.0,  False),
    ("Microsoft",        "Technology",        "Hyderabad",  35.0,  False),
    ("Zoho",             "SaaS",              "Chennai",    14.0,  False),
    ("Byju's",           "EdTech",            "Bangalore",  8.5,   True),
    ("Swiggy",           "Food Tech",         "Bangalore",  15.0,  False),
    ("Ola",              "Transport Tech",    "Bangalore",  12.5,  False),
    ("L&T Infotech",     "IT Services",       "Mumbai",     11.0,  False),
    ("Mindtree",         "IT Consulting",     "Bangalore",  12.0,  False),
    ("BOSCH",            "Automotive Tech",   "Bangalore",  18.0,  False),
    ("ABB India",        "Electrical",        "Bangalore",  14.0,  False),
    ("Siemens",          "Engineering",       "Pune",       16.0,  False),
    ("Larsen & Toubro",  "Construction",      "Mumbai",     13.0,  False),
    ("Tata Motors",      "Automotive",        "Pune",       12.0,  False),
    ("BHEL",             "Power",             "Delhi",      11.0,  True),
    ("Samsung R&D",      "Electronics",       "Bangalore",  22.0,  False),
]

ROLES_BY_BRANCH = {
    "Computer Science":    ["Software Engineer","Backend Developer","Data Analyst","Full Stack Developer","ML Engineer"],
    "Information Science": ["Software Engineer","System Analyst","Web Developer","Database Administrator"],
    "Electronics":         ["Embedded Engineer","VLSI Design Engineer","IoT Engineer","Hardware Engineer"],
    "Mechanical":          ["Design Engineer","Production Engineer","Quality Analyst","Project Engineer"],
    "Civil":               ["Site Engineer","Structural Engineer","Project Coordinator","CAD Engineer"],
    "Electrical":          ["Electrical Engineer","Power Systems Engineer","Control Engineer","Field Engineer"],
}

SKILLS_BY_BRANCH = {
    "Computer Science":    ["Python","Java","React","MySQL","Machine Learning","Git","Django","AWS"],
    "Information Science": ["Java","Python","MySQL","PHP","JavaScript","Linux","Networking"],
    "Electronics":         ["C","C++","Embedded C","MATLAB","VHDL","IoT","Arduino","PCB Design"],
    "Mechanical":          ["AutoCAD","CATIA","SolidWorks","ANSYS","Manufacturing","CNC"],
    "Civil":               ["AutoCAD","STAAD Pro","Revit","MS Project","Surveying","GIS"],
    "Electrical":          ["MATLAB","PLC","SCADA","AutoCAD Electrical","Power Systems","HV Testing"],
}

YEARS = [2021, 2022, 2023, 2024, 2025]

def make_hash(pw):
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()

def rand_cgpa(placed):
    if placed:
        return round(random.uniform(6.5, 9.8), 2)
    return round(random.uniform(5.0, 7.5), 2)

def rand_date(year):
    start = date(year, 6, 1)
    return start + timedelta(days=random.randint(0, 180))

def main():
    app = create_app("development")
    with app.app_context():
        db.create_all()

        print("Seeding companies...")
        company_map = {}
        for name, industry, location, pkg, is_off in COMPANIES_DATA:
            c = Company.query.filter_by(name=name).first()
            if not c:
                c = Company(name=name, industry=industry, location=location,
                            contact_email=f"hr@{name.lower().replace(' ','')}.com")
                db.session.add(c)
                db.session.flush()
            company_map[name] = (c, pkg, is_off)
        db.session.commit()
        print(f"  {len(company_map)} companies ready")

        total_students = 0
        total_placed = 0

        for year in YEARS:
            print(f"\nSeeding year {year}...")
            for branch, info in BRANCHES.items():
                n_total = info["total"]
                n_placed = int(n_total * info["place_rate"])
                skills = SKILLS_BY_BRANCH[branch]
                roles = ROLES_BY_BRANCH[branch]

                # Companies relevant to this branch
                if branch in ("Mechanical","Civil"):
                    eligible_cos = [(n,c,p,o) for n,(c,p,o) in company_map.items()
                                    if any(k in c.industry for k in ["Engineering","Construction","Automotive","Power"])]
                elif branch == "Electrical":
                    eligible_cos = [(n,c,p,o) for n,(c,p,o) in company_map.items()
                                    if any(k in c.industry for k in ["Electrical","Power","Engineering"])]
                elif branch == "Electronics":
                    eligible_cos = [(n,c,p,o) for n,(c,p,o) in company_map.items()
                                    if any(k in c.industry for k in ["Electronics","Automotive","Technology","IT"])]
                else:
                    eligible_cos = [(n,c,p,o) for n,(c,p,o) in company_map.items()
                                    if any(k in c.industry for k in ["IT","Technology","SaaS","EdTech","Food","Transport","E-Commerce"])]

                if not eligible_cos:
                    eligible_cos = list(company_map.items())[:5]
                    eligible_cos = [(n,c,p,o) for n,(c,p,o) in eligible_cos]

                placed_so_far = 0
                for i in range(n_total):
                    is_placed = placed_so_far < n_placed and random.random() < info["place_rate"]
                    cgpa = rand_cgpa(is_placed)

                    branch_code = branch.replace(" ","_").lower()[:5]
                    email = f"s{year}{branch_code}{i+1}@atmece.edu"
                    try:
                        existing = User.query.filter_by(email=email).first()
                    except Exception:
                        db.session.rollback()
                        continue
                    if existing:
                        if existing.profile and existing.profile.graduation_year == year:
                            if PlacementRecord.query.filter_by(profile_id=existing.profile.id).first():
                                placed_so_far += 1
                                total_placed += 1
                        total_students += 1
                        continue

                    u = User(name=f"{branch[:4]} Student {year}-{i+1}",
                             email=email,
                             password_hash=make_hash("Student@123"),
                             role="student", status="active")
                    db.session.add(u)
                    db.session.flush()

                    num_skills = random.randint(3, len(skills))
                    chosen_skills = random.sample(skills, num_skills)

                    p = StudentProfile(
                        user_id=u.id,
                        institution="ATMECE, Mysore",
                        degree="B.E",
                        branch=branch,
                        cgpa=cgpa,
                        graduation_year=year,
                        skills_json=json.dumps(chosen_skills),
                        dream_job=random.choice(roles),
                        expected_lpa=round(random.uniform(5, 20), 1),
                    )
                    db.session.add(p)
                    db.session.flush()

                    # Add 1-2 projects
                    proj_title = f"{random.choice(roles)} Project"
                    db.session.add(Project(
                        profile_id=p.id,
                        title=proj_title,
                        description=f"Developed a {proj_title.lower()} using {', '.join(chosen_skills[:3])}.",
                        technologies=", ".join(chosen_skills[:3]),
                    ))

                    # Placement record
                    if is_placed and eligible_cos:
                        co_name, co, pkg, is_off = random.choice(eligible_cos)
                        role_title = random.choice(roles)

                        # Find or create job role
                        jr = JobRole.query.filter_by(company_id=co.id, title=role_title).first()
                        if not jr:
                            jr = JobRole(
                                company_id=co.id,
                                title=role_title,
                                description=f"{role_title} at {co_name}",
                                required_skills_json=json.dumps(chosen_skills[:3]),
                                cgpa_threshold=6.0,
                                is_active=True,
                            )
                            db.session.add(jr)
                            db.session.flush()

                        actual_pkg = round(pkg * random.uniform(0.85, 1.15), 1)
                        pr = PlacementRecord(
                            profile_id=p.id,
                            job_role_id=jr.id,
                            company_id=co.id,
                            placement_date=rand_date(year),
                            department=branch,
                            package_lpa=actual_pkg,
                            notes="off-campus" if is_off else "on-campus",
                        )
                        db.session.add(pr)
                        placed_so_far += 1
                        total_placed += 1

                    total_students += 1

                db.session.commit()
                print(f"  {branch}: {n_total} students, {placed_so_far} placed")

        print(f"\n{'='*50}")
        print(f"  Total students seeded : {total_students}")
        print(f"  Total placed          : {total_placed}")
        print(f"  Overall rate          : {total_placed/total_students*100:.1f}%")
        print(f"  Years                 : {YEARS}")
        print(f"{'='*50}\n")

if __name__ == "__main__":
    main()
