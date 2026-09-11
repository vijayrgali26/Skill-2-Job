"""Seed script for the Skill2Job Placement System.

Populates the database with:
- Skill taxonomy entries across 6 categories with synonym mappings
- A default admin user account

This script is idempotent — safe to run multiple times.

Usage:
    python seed.py
"""

import json
import sys
import os

# Ensure the backend directory is on the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import bcrypt
from dotenv import load_dotenv

load_dotenv()

from app import create_app, db
from app.models import User, SkillTaxonomy


# ---------------------------------------------------------------------------
# Skill taxonomy data
# ---------------------------------------------------------------------------

SKILL_TAXONOMY = [
    # Programming Languages
    {"canonical_name": "Python", "category": "Programming Languages", "synonyms": ["py", "python3"]},
    {"canonical_name": "JavaScript", "category": "Programming Languages", "synonyms": ["JS", "js", "javascript"]},
    {"canonical_name": "Java", "category": "Programming Languages", "synonyms": ["java"]},
    {"canonical_name": "C++", "category": "Programming Languages", "synonyms": ["cpp", "c plus plus"]},
    {"canonical_name": "C#", "category": "Programming Languages", "synonyms": ["C Sharp", "c sharp", "csharp"]},
    {"canonical_name": "TypeScript", "category": "Programming Languages", "synonyms": ["TS", "ts"]},
    {"canonical_name": "Go", "category": "Programming Languages", "synonyms": ["golang", "Golang"]},
    {"canonical_name": "Ruby", "category": "Programming Languages", "synonyms": ["rb"]},
    {"canonical_name": "PHP", "category": "Programming Languages", "synonyms": ["php"]},
    {"canonical_name": "Rust", "category": "Programming Languages", "synonyms": ["rust-lang"]},

    # Frameworks
    {"canonical_name": "React", "category": "Frameworks", "synonyms": ["ReactJS", "reactjs", "react.js"]},
    {"canonical_name": "Angular", "category": "Frameworks", "synonyms": ["AngularJS", "angular"]},
    {"canonical_name": "Vue.js", "category": "Frameworks", "synonyms": ["VueJS", "vuejs", "vue"]},
    {"canonical_name": "Django", "category": "Frameworks", "synonyms": ["django"]},
    {"canonical_name": "Flask", "category": "Frameworks", "synonyms": ["flask"]},
    {"canonical_name": "Spring Boot", "category": "Frameworks", "synonyms": ["spring", "springboot"]},
    {"canonical_name": "Express.js", "category": "Frameworks", "synonyms": ["express", "expressjs"]},
    {"canonical_name": ".NET", "category": "Frameworks", "synonyms": ["dotnet", "dot net"]},
    {"canonical_name": "FastAPI", "category": "Frameworks", "synonyms": ["fastapi"]},

    # Databases
    {"canonical_name": "MySQL", "category": "Databases", "synonyms": ["mysql"]},
    {"canonical_name": "PostgreSQL", "category": "Databases", "synonyms": ["Postgres", "postgres", "psql"]},
    {"canonical_name": "MongoDB", "category": "Databases", "synonyms": ["Mongo", "mongo"]},
    {"canonical_name": "Redis", "category": "Databases", "synonyms": ["redis"]},
    {"canonical_name": "SQLite", "category": "Databases", "synonyms": ["sqlite", "sqlite3"]},
    {"canonical_name": "Oracle", "category": "Databases", "synonyms": ["oracle db", "oracledb"]},
    {"canonical_name": "Cassandra", "category": "Databases", "synonyms": ["cassandra", "apache cassandra"]},

    # Tools
    {"canonical_name": "Docker", "category": "Tools", "synonyms": ["docker"]},
    {"canonical_name": "Kubernetes", "category": "Tools", "synonyms": ["K8s", "k8s"]},
    {"canonical_name": "Git", "category": "Tools", "synonyms": ["git"]},
    {"canonical_name": "Jenkins", "category": "Tools", "synonyms": ["jenkins"]},
    {"canonical_name": "AWS", "category": "Tools", "synonyms": ["Amazon Web Services", "aws"]},
    {"canonical_name": "Azure", "category": "Tools", "synonyms": ["Microsoft Azure", "azure"]},
    {"canonical_name": "GCP", "category": "Tools", "synonyms": ["Google Cloud Platform", "Google Cloud", "gcp"]},
    {"canonical_name": "Terraform", "category": "Tools", "synonyms": ["terraform", "tf"]},
    {"canonical_name": "Ansible", "category": "Tools", "synonyms": ["ansible"]},

    # Soft Skills
    {"canonical_name": "Communication", "category": "Soft Skills", "synonyms": ["communication skills"]},
    {"canonical_name": "Leadership", "category": "Soft Skills", "synonyms": ["leadership skills"]},
    {"canonical_name": "Teamwork", "category": "Soft Skills", "synonyms": ["team work", "collaboration"]},
    {"canonical_name": "Problem Solving", "category": "Soft Skills", "synonyms": ["problem-solving", "analytical thinking"]},
    {"canonical_name": "Time Management", "category": "Soft Skills", "synonyms": ["time-management"]},

    # Domain Knowledge
    {"canonical_name": "Machine Learning", "category": "Domain Knowledge", "synonyms": ["ML", "ml"]},
    {"canonical_name": "Data Science", "category": "Domain Knowledge", "synonyms": ["DS", "ds", "data analytics"]},
    {"canonical_name": "Cloud Computing", "category": "Domain Knowledge", "synonyms": ["cloud", "cloud infrastructure"]},
    {"canonical_name": "Cybersecurity", "category": "Domain Knowledge", "synonyms": ["cyber security", "infosec", "information security"]},
    {"canonical_name": "DevOps", "category": "Domain Knowledge", "synonyms": ["devops", "dev ops"]},
]


# ---------------------------------------------------------------------------
# Default admin account
# ---------------------------------------------------------------------------

ADMIN_EMAIL = "admin@skill2job.com"
ADMIN_NAME = "System Admin"
ADMIN_PASSWORD = "Admin@123"  # Default password — change in production


def seed_skill_taxonomy():
    """Insert or update skill taxonomy entries (idempotent)."""
    count_new = 0
    count_existing = 0

    for entry in SKILL_TAXONOMY:
        existing = SkillTaxonomy.query.filter_by(
            canonical_name=entry["canonical_name"]
        ).first()

        if existing:
            # Update synonyms and category if the entry already exists
            existing.category = entry["category"]
            existing.synonyms_json = json.dumps(entry["synonyms"])
            count_existing += 1
        else:
            skill = SkillTaxonomy(
                canonical_name=entry["canonical_name"],
                category=entry["category"],
                synonyms_json=json.dumps(entry["synonyms"]),
                is_deprecated=False,
            )
            db.session.add(skill)
            count_new += 1

    db.session.commit()
    print(f"  Skill taxonomy: {count_new} new, {count_existing} updated "
          f"({len(SKILL_TAXONOMY)} total)")


def seed_admin_user():
    """Create the default admin account if it doesn't exist (idempotent)."""
    existing = User.query.filter_by(email=ADMIN_EMAIL).first()

    if existing:
        print(f"  Admin user already exists: {ADMIN_EMAIL}")
        return

    password_hash = bcrypt.hashpw(
        ADMIN_PASSWORD.encode("utf-8"),
        bcrypt.gensalt(),
    ).decode("utf-8")

    admin = User(
        name=ADMIN_NAME,
        email=ADMIN_EMAIL,
        password_hash=password_hash,
        role="admin",
        status="active",
    )
    db.session.add(admin)
    db.session.commit()
    print(f"  Admin user created: {ADMIN_EMAIL}")


def main():
    """Run the seed script."""
    app = create_app("development")

    with app.app_context():
        print("Creating database tables...")
        db.create_all()
        print("Tables created.\n")

        print("Seeding skill taxonomy...")
        seed_skill_taxonomy()

        print("Seeding admin user...")
        seed_admin_user()

        print("\nSeed complete.")


if __name__ == "__main__":
    main()
