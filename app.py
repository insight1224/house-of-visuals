#!/usr/bin/env python3
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import argparse
import csv
import io
import hashlib
import hmac
from datetime import datetime, timedelta
from html import escape
import json
import os
import re
import smtplib
import sqlite3
import ssl
from email.message import EmailMessage
from urllib.parse import parse_qs, quote_plus
import urllib.request
import urllib.error


PROJECT_DIR = Path(__file__).resolve().parent
INQUIRY_DIR = PROJECT_DIR / "inquiries"
TESTIMONIAL_DIR = PROJECT_DIR / "testimonials"
DEFAULT_LEAD_STATUSES = ["New", "Contacted", "Interested", "Proposal Sent", "Won", "Lost", "Completed"]
VALID_LEAD_STATUSES = set(DEFAULT_LEAD_STATUSES)

DEFAULT_PROSPECT_STATUSES = [
    "New Prospect",
    "Needs Review",
    "Ready to Contact",
    "Contacted",
    "Follow-Up Needed",
    "No Response",
    "Interested",
    "Not Interested",
    "Converted to Lead",
]
VALID_PROSPECT_STATUSES = set(DEFAULT_PROSPECT_STATUSES)

DEFAULT_UPWORK_SCOUT_STATUSES = [
    "New",
    "Applied",
    "Maybe",
    "Skipped",
    "Interview",
    "Hired",
    "Lost",
]
VALID_UPWORK_SCOUT_STATUSES = set(DEFAULT_UPWORK_SCOUT_STATUSES)

CLIENT_PREVIEWS = [
    {
        "client": "Creative Impressions Media",
        "slug": "creative-impressions",
        "type": "Website preview",
        "status": "In Review",
        "booking_link": "https://calendar.app.google/kkKWCQk94dLb3psH8",
        "has_preview": True,
        "has_demo": True,
        "has_feedback": True,
    },
    {
        "client": "Jukebox Lounge NC",
        "slug": "jukebox-lounge",
        "type": "Website / dashboard preview",
        "status": "Coming Soon",
        "booking_link": "https://calendar.app.google/kkKWCQk94dLb3psH8",
        "has_preview": False,
        "has_demo": False,
        "has_feedback": False,
    },
]



def load_env_files():
    for env_path in [PROJECT_DIR.parent / ".env", PROJECT_DIR / ".env"]:
        if not env_path.exists():
            continue
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env_files()


def get_database_path():
    return Path(os.getenv("HOV_DB_PATH", PROJECT_DIR / "leads.db"))


def db_connect():
    connection = sqlite3.connect(get_database_path())
    connection.row_factory = sqlite3.Row
    return connection


def init_database():
    with db_connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS businesses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                notification_email TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                business_id INTEGER NOT NULL,
                source_form TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'New',
                internal_notes TEXT NOT NULL DEFAULT '',
                submitted_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                full_name TEXT,
                business_name TEXT,
                email TEXT,
                phone TEXT,
                website_social TEXT,
                project_types TEXT,
                project_goals TEXT,
                timeline TEXT,
                budget TEXT,
                referral_source TEXT,
                fields_json TEXT NOT NULL,
                email_status TEXT NOT NULL DEFAULT 'pending',
                email_error TEXT,
                FOREIGN KEY (business_id) REFERENCES businesses(id)
            )
            """
        )
        connection.execute("CREATE INDEX IF NOT EXISTS idx_leads_business ON leads (business_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_leads_status ON leads (status)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_leads_submitted_at ON leads (submitted_at)")

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS prospects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                business_name TEXT NOT NULL,
                contact_name TEXT,
                industry TEXT,
                city_state TEXT,
                website TEXT,
                instagram TEXT,
                facebook TEXT,
                email TEXT,
                phone TEXT,
                website_status TEXT,
                potential_need TEXT,
                suggested_offer TEXT,
                recommended_demo TEXT,
                lead_score INTEGER NOT NULL DEFAULT 0,
                review_priority TEXT NOT NULL DEFAULT 'Manual Review',
                why_this_prospect TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'New Prospect',
                notes TEXT NOT NULL DEFAULT '',
                last_contacted TEXT,
                next_follow_up TEXT,
                last_contact_method TEXT,
                added_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS client_previews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                business_name TEXT NOT NULL,
                demo_link TEXT NOT NULL,
                loom_link TEXT,
                notes TEXT NOT NULL DEFAULT '',
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute("CREATE INDEX IF NOT EXISTS idx_client_previews_active ON client_previews (is_active)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_client_previews_created_at ON client_previews (created_at)")

        columns = [row["name"] for row in connection.execute("PRAGMA table_info(prospects)").fetchall()]
        if "next_follow_up" not in columns:
            connection.execute("ALTER TABLE prospects ADD COLUMN next_follow_up TEXT")
        if "review_priority" not in columns:
            connection.execute("ALTER TABLE prospects ADD COLUMN review_priority TEXT NOT NULL DEFAULT 'Manual Review'")
        if "why_this_prospect" not in columns:
            connection.execute("ALTER TABLE prospects ADD COLUMN why_this_prospect TEXT NOT NULL DEFAULT ''")
        if "last_contact_method" not in columns:
            connection.execute("ALTER TABLE prospects ADD COLUMN last_contact_method TEXT")

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS prospect_outreach_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prospect_id INTEGER NOT NULL,
                activity_type TEXT NOT NULL,
                contact_method TEXT NOT NULL,
                contacted_at TEXT NOT NULL,
                next_follow_up TEXT,
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                FOREIGN KEY (prospect_id) REFERENCES prospects(id) ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_outreach_history_prospect "
            "ON prospect_outreach_history (prospect_id)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_outreach_history_contacted_at "
            "ON prospect_outreach_history (contacted_at)"
        )

        connection.execute("CREATE INDEX IF NOT EXISTS idx_prospects_status ON prospects (status)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_prospects_industry ON prospects (industry)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_prospects_added_at ON prospects (added_at)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_prospects_next_follow_up ON prospects (next_follow_up)")

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS upwork_scout_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                client_name TEXT NOT NULL DEFAULT '',
                source TEXT NOT NULL DEFAULT 'Manual Paste',
                job_url TEXT NOT NULL DEFAULT '',
                pasted_text TEXT NOT NULL DEFAULT '',
                budget TEXT NOT NULL DEFAULT '',
                connects_required TEXT NOT NULL DEFAULT '',
                proposals_count TEXT NOT NULL DEFAULT '',
                interviews_count TEXT NOT NULL DEFAULT '',
                posted_date TEXT NOT NULL DEFAULT '',
                last_viewed TEXT NOT NULL DEFAULT '',
                client_rating TEXT NOT NULL DEFAULT '',
                client_spend TEXT NOT NULL DEFAULT '',
                skills TEXT NOT NULL DEFAULT '',
                score INTEGER NOT NULL DEFAULT 0,
                decision_label TEXT NOT NULL DEFAULT 'Maybe',
                short_reason TEXT NOT NULL DEFAULT '',
                positive_signs TEXT NOT NULL DEFAULT '[]',
                red_flags TEXT NOT NULL DEFAULT '[]',
                suggested_bid TEXT NOT NULL DEFAULT '',
                suggested_timeline TEXT NOT NULL DEFAULT '',
                suggested_portfolio TEXT NOT NULL DEFAULT '[]',
                proposal_draft TEXT NOT NULL DEFAULT '',
                client_questions TEXT NOT NULL DEFAULT '[]',
                status TEXT NOT NULL DEFAULT 'New',
                connects_spent TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute("CREATE INDEX IF NOT EXISTS idx_upwork_scout_score ON upwork_scout_jobs (score)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_upwork_scout_decision ON upwork_scout_jobs (decision_label)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_upwork_scout_status ON upwork_scout_jobs (status)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_upwork_scout_created_at ON upwork_scout_jobs (created_at)")


def get_business_id():
    business_key = os.getenv("HOV_BUSINESS_KEY", "house-of-visuals")
    business_name = os.getenv("HOV_BUSINESS_NAME", "House of Visuals")
    notification_email = os.getenv("HOV_INQUIRY_TO", "hello@houseofvisualsco.com")
    now = datetime.now().isoformat(timespec="seconds")
    with db_connect() as connection:
        connection.execute(
            """
            INSERT INTO businesses (key, name, notification_email, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                name = excluded.name,
                notification_email = excluded.notification_email
            """,
            (business_key, business_name, notification_email, now),
        )
        row = connection.execute("SELECT id FROM businesses WHERE key = ?", (business_key,)).fetchone()
        return row["id"]


def first(fields, name):
    values = fields.get(name, [])
    return values[0].strip() if values else ""


def first_of(fields, *names):
    for name in names:
        value = first(fields, name)
        if value:
            return value
    return ""


def many(fields, name):
    return [value.strip() for value in fields.get(name, []) if value.strip()]


def fields_to_plain_dict(fields):
    return {key: values if len(values) > 1 else values[0] for key, values in fields.items()}


def create_lead(fields, source_form="house-of-visuals-contact"):
    init_database()
    business_id = get_business_id()
    now = datetime.now().isoformat(timespec="seconds")
    project_types = many(fields, "project_type[]")
    project_goals = many(fields, "project_goal[]")
    with db_connect() as connection:
        cursor = connection.execute(
            """
            INSERT INTO leads (
                business_id, source_form, status, internal_notes, submitted_at, updated_at,
                full_name, business_name, email, phone, website_social, project_types,
                project_goals, timeline, budget, referral_source, fields_json
            )
            VALUES (?, ?, 'New', '', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                business_id,
                source_form,
                now,
                now,
                first(fields, "full_name"),
                first(fields, "business_name"),
                first(fields, "email"),
                first(fields, "phone"),
                first_of(fields, "website_social_links", "website_social"),
                json.dumps(project_types),
                json.dumps(project_goals),
                first(fields, "timeline"),
                first(fields, "budget"),
                first(fields, "referral_source"),
                json.dumps(fields_to_plain_dict(fields), indent=2),
            ),
        )
        return cursor.lastrowid


def update_lead_email_status(lead_id, status, error=""):
    with db_connect() as connection:
        connection.execute(
            "UPDATE leads SET email_status = ?, email_error = ?, updated_at = ? WHERE id = ?",
            (status, error, datetime.now().isoformat(timespec="seconds"), lead_id),
        )


def row_to_lead(row):
    lead = dict(row)
    lead["project_types"] = json.loads(lead.get("project_types") or "[]")
    lead["project_goals"] = json.loads(lead.get("project_goals") or "[]")
    lead["fields"] = json.loads(lead.pop("fields_json") or "{}")
    return lead


def get_leads():
    init_database()
    with db_connect() as connection:
        rows = connection.execute(
            """
            SELECT leads.*, businesses.name AS owner_business_name
            FROM leads
            JOIN businesses ON businesses.id = leads.business_id
            ORDER BY submitted_at DESC, id DESC
            """
        ).fetchall()
        return [row_to_lead(row) for row in rows]


def get_lead(lead_id):
    init_database()
    with db_connect() as connection:
        row = connection.execute(
            """
            SELECT leads.*, businesses.name AS owner_business_name
            FROM leads
            JOIN businesses ON businesses.id = leads.business_id
            WHERE leads.id = ?
            """,
            (lead_id,),
        ).fetchone()
        return row_to_lead(row) if row else None


def update_lead(lead_id, status, internal_notes):
    if status not in VALID_LEAD_STATUSES:
        raise ValueError("Invalid lead status.")
    with db_connect() as connection:
        connection.execute(
            "UPDATE leads SET status = ?, internal_notes = ?, updated_at = ? WHERE id = ?",
            (status, internal_notes, datetime.now().isoformat(timespec="seconds"), lead_id),
        )


def delete_lead(lead_id):
    init_database()
    with db_connect() as connection:
        connection.execute("DELETE FROM leads WHERE id = ?", (lead_id,))


def delete_prospect(prospect_id):
    init_database()
    with db_connect() as connection:
        connection.execute("DELETE FROM prospects WHERE id = ?", (prospect_id,))




def row_to_upwork_scout_job(row):
    job = dict(row)
    for key in ["positive_signs", "red_flags", "suggested_portfolio", "client_questions"]:
        try:
            job[key] = json.loads(job.get(key) or "[]")
        except json.JSONDecodeError:
            job[key] = []
    return job


def get_upwork_scout_jobs(status_filter="", decision_filter="", sort_by="created_at"):
    init_database()

    allowed_sorts = {
        "created_at": "created_at DESC, id DESC",
        "score": "score DESC, created_at DESC",
        "connects": "connects_required ASC, score DESC",
        "status": "status ASC, created_at DESC",
    }
    order_by = allowed_sorts.get(sort_by, allowed_sorts["created_at"])

    where = []
    params = []

    if status_filter:
        where.append("status = ?")
        params.append(status_filter)

    if decision_filter:
        where.append("decision_label = ?")
        params.append(decision_filter)

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    with db_connect() as connection:
        rows = connection.execute(
            f"""
            SELECT *
            FROM upwork_scout_jobs
            {where_sql}
            ORDER BY {order_by}
            """,
            params,
        ).fetchall()
        return [row_to_upwork_scout_job(row) for row in rows]


def create_upwork_scout_job(job, job_url="", status="New", notes="", connects_spent=""):
    init_database()

    if status not in VALID_UPWORK_SCOUT_STATUSES:
        status = "New"

    now = datetime.now().isoformat(timespec="seconds")

    with db_connect() as connection:
        cursor = connection.execute(
            """
            INSERT INTO upwork_scout_jobs (
                title, client_name, source, job_url, pasted_text, budget,
                connects_required, proposals_count, interviews_count, posted_date,
                last_viewed, client_rating, client_spend, skills, score,
                decision_label, short_reason, positive_signs, red_flags,
                suggested_bid, suggested_timeline, suggested_portfolio,
                proposal_draft, client_questions, status, connects_spent,
                notes, created_at, updated_at
            )
            VALUES (?, '', 'Manual Paste', ?, ?, ?, ?, ?, ?, '', '', '', '', '', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job.get("title") or "Upwork Job",
                job_url or "",
                job.get("pasted_text") or "",
                job.get("budget") or "",
                str(job.get("connects_required") or ""),
                str(job.get("proposals") or ""),
                str(job.get("interviews") or ""),
                int(job.get("score") or 0),
                job.get("decision") or "Maybe",
                job.get("short_reason") or "",
                json.dumps(job.get("positive_signs") or []),
                json.dumps(job.get("red_flags") or []),
                job.get("suggested_bid") or "",
                job.get("suggested_timeline") or "",
                json.dumps(job.get("suggested_portfolio") or []),
                job.get("proposal_draft") or "",
                json.dumps(job.get("client_questions") or []),
                status,
                connects_spent or "",
                notes or "",
                now,
                now,
            ),
        )
        return cursor.lastrowid


def update_upwork_scout_job(job_id, status=None, notes=None, connects_spent=None, job_url=None):
    init_database()

    updates = []
    params = []

    if status is not None:
        if status not in VALID_UPWORK_SCOUT_STATUSES:
            raise ValueError("Invalid Upwork Scout status.")
        updates.append("status = ?")
        params.append(status)

    if notes is not None:
        updates.append("notes = ?")
        params.append(notes)

    if connects_spent is not None:
        updates.append("connects_spent = ?")
        params.append(connects_spent)

    if job_url is not None:
        updates.append("job_url = ?")
        params.append(job_url)

    if not updates:
        return

    updates.append("updated_at = ?")
    params.append(datetime.now().isoformat(timespec="seconds"))
    params.append(job_id)

    with db_connect() as connection:
        connection.execute(
            f"UPDATE upwork_scout_jobs SET {', '.join(updates)} WHERE id = ?",
            params,
        )


CONTACT_METHODS = [
    "Email",
    "Website Contact Form",
    "Instagram",
    "Facebook",
    "Phone",
    "Text Message",
    "LinkedIn",
    "Other",
]


def get_prospect_outreach_history(prospect_id):
    init_database()
    with db_connect() as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM prospect_outreach_history
            WHERE prospect_id = ?
            ORDER BY contacted_at DESC, id DESC
            """,
            (prospect_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def log_prospect_contact(
    prospect_id,
    activity_type,
    contact_method,
    follow_up_days=3,
    notes="",
):
    init_database()

    if contact_method not in CONTACT_METHODS:
        raise ValueError("Invalid contact method.")

    if activity_type not in {"Initial Contact", "Follow-Up"}:
        raise ValueError("Invalid outreach activity type.")

    try:
        follow_up_days = int(follow_up_days)
    except (TypeError, ValueError):
        follow_up_days = 3

    today = datetime.now()
    contacted_date = today.strftime("%Y-%m-%d")

    if follow_up_days > 0:
        next_follow_up = (today + timedelta(days=follow_up_days)).strftime("%Y-%m-%d")
    else:
        next_follow_up = None

    if activity_type == "Initial Contact":
        status = "Contacted"
    elif follow_up_days > 0:
        status = "Follow-Up Needed"
    else:
        status = "No Response"

    timestamp = today.isoformat(timespec="seconds")

    with db_connect() as connection:
        existing = connection.execute(
            "SELECT id FROM prospects WHERE id = ?",
            (prospect_id,),
        ).fetchone()

        if not existing:
            raise ValueError("Prospect not found.")

        connection.execute(
            """
            UPDATE prospects
            SET status = ?,
                last_contacted = ?,
                next_follow_up = ?,
                last_contact_method = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                status,
                contacted_date,
                next_follow_up,
                contact_method,
                timestamp,
                prospect_id,
            ),
        )

        connection.execute(
            """
            INSERT INTO prospect_outreach_history (
                prospect_id,
                activity_type,
                contact_method,
                contacted_at,
                next_follow_up,
                notes,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                prospect_id,
                activity_type,
                contact_method,
                contacted_date,
                next_follow_up,
                notes or "",
                timestamp,
            ),
        )

    return {
        "status": status,
        "last_contacted": contacted_date,
        "next_follow_up": next_follow_up,
        "last_contact_method": contact_method,
    }


def mark_prospect_no_response(prospect_id):
    init_database()
    timestamp = datetime.now().isoformat(timespec="seconds")

    with db_connect() as connection:
        existing = connection.execute(
            "SELECT id FROM prospects WHERE id = ?",
            (prospect_id,),
        ).fetchone()

        if not existing:
            raise ValueError("Prospect not found.")

        connection.execute(
            """
            UPDATE prospects
            SET status = 'No Response',
                next_follow_up = NULL,
                updated_at = ?
            WHERE id = ?
            """,
            (timestamp, prospect_id),
        )


def create_prospect(fields):
    init_database()
    now = datetime.now().isoformat(timespec="seconds")
    try:
        lead_score = int(first(fields, "lead_score") or "0")
    except ValueError:
        lead_score = 0
    lead_score = max(0, min(10, lead_score))

    status = first(fields, "status") or "New Prospect"
    if status not in VALID_PROSPECT_STATUSES:
        status = "New Prospect"

    with db_connect() as connection:
        cursor = connection.execute(
            """
                        INSERT INTO prospects (
                business_name, contact_name, industry, city_state, website, instagram,
                facebook, email, phone, website_status, potential_need, suggested_offer,
                recommended_demo, lead_score, review_priority, why_this_prospect, status, notes, last_contacted, next_follow_up, added_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                first(fields, "business_name") or "Unnamed Business",
                first(fields, "contact_name"),
                first(fields, "industry"),
                first(fields, "city_state"),
                first(fields, "website"),
                first(fields, "instagram"),
                first(fields, "facebook"),
                first(fields, "email"),
                first(fields, "phone"),
                first(fields, "website_status"),
                first(fields, "potential_need"),
                first(fields, "suggested_offer"),
                first(fields, "recommended_demo"),
                lead_score,
                first(fields, "review_priority") or "Manual Review",
                first(fields, "why_this_prospect"),
                status,
                first(fields, "notes"),
                first(fields, "last_contacted"),
                first(fields, "next_follow_up"),
                now,
                now,
            ),
        )
        return cursor.lastrowid


def get_prospects():
    init_database()
    with db_connect() as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM prospects
            ORDER BY updated_at DESC, added_at DESC, id DESC
            """
        ).fetchall()
        return [dict(row) for row in rows]


def get_prospect(prospect_id):
    init_database()
    with db_connect() as connection:
        row = connection.execute("SELECT * FROM prospects WHERE id = ?", (prospect_id,)).fetchone()
        return dict(row) if row else None


def update_prospect(prospect_id, fields):
    status = first(fields, "status") or "New Prospect"
    if status not in VALID_PROSPECT_STATUSES:
        raise ValueError("Invalid prospect status.")

    try:
        lead_score = int(first(fields, "lead_score") or "0")
    except ValueError:
        lead_score = 0
    lead_score = max(0, min(10, lead_score))

    with db_connect() as connection:
        connection.execute(
            """
            UPDATE prospects
            SET business_name = ?, contact_name = ?, industry = ?, city_state = ?,
                website = ?, instagram = ?, facebook = ?, email = ?, phone = ?,
                website_status = ?, potential_need = ?, suggested_offer = ?,
                recommended_demo = ?, lead_score = ?, review_priority = ?, why_this_prospect = ?,
                status = ?, notes = ?, last_contacted = ?, next_follow_up = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                first(fields, "business_name") or "Unnamed Business",
                first(fields, "contact_name"),
                first(fields, "industry"),
                first(fields, "city_state"),
                first(fields, "website"),
                first(fields, "instagram"),
                first(fields, "facebook"),
                first(fields, "email"),
                first(fields, "phone"),
                first(fields, "website_status"),
                first(fields, "potential_need"),
                first(fields, "suggested_offer"),
                first(fields, "recommended_demo"),
                lead_score,
                first(fields, "review_priority") or "Manual Review",
                first(fields, "why_this_prospect"),
                status,
                first(fields, "notes"),
                first(fields, "last_contacted"),
                first(fields, "next_follow_up"),
                datetime.now().isoformat(timespec="seconds"),
                prospect_id,
            ),
        )


def sync_client_preview_folders():
    """Automatically add client-preview folders to the admin directory."""
    preview_root = PROJECT_DIR / "client-preview"

    if not preview_root.exists():
        return

    init_database()

    with db_connect() as connection:
        existing_links = {
            (row["demo_link"] or "").rstrip("/")
            for row in connection.execute(
                "SELECT demo_link FROM client_previews"
            ).fetchall()
        }

        now = datetime.now().isoformat(timespec="seconds")

        for folder in sorted(preview_root.iterdir()):
            if not folder.is_dir() or folder.name.startswith("."):
                continue

            slug = folder.name
            demo_link = f"/client-preview/{slug}/"
            client_path = f"/client-preview/{slug}/"

            already_exists = any(
                existing_link == client_path.rstrip("/")
                or existing_link.startswith(client_path.rstrip("/") + "/")
                for existing_link in existing_links
            )

            if already_exists:
                continue

            business_name = slug.replace("-", " ").replace("_", " ").title()

            connection.execute(
                """
                INSERT INTO client_previews (
                    business_name,
                    demo_link,
                    loom_link,
                    notes,
                    is_active,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, '', '', 1, ?, ?)
                """,
                (business_name, demo_link, now, now),
            )

            existing_links.add(demo_link.rstrip("/"))


def create_client_preview(fields):
    business_name = first(fields, "business_name") or "Unnamed Business"
    demo_link = first(fields, "demo_link")
    loom_link = first(fields, "loom_link")
    notes = first(fields, "notes")
    now = datetime.now().isoformat(timespec="seconds")

    if not demo_link:
        raise ValueError("Demo link is required.")

    init_database()
    with db_connect() as connection:
        cursor = connection.execute(
            """
            INSERT INTO client_previews (
                business_name, demo_link, loom_link, notes,
                is_active, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, 1, ?, ?)
            """,
            (business_name, demo_link, loom_link, notes, now, now),
        )
        return cursor.lastrowid


def get_client_previews(include_inactive=True):
    init_database()
    with db_connect() as connection:
        if include_inactive:
            rows = connection.execute(
                """
                SELECT * FROM client_previews
                ORDER BY is_active DESC, created_at DESC
                """
            ).fetchall()
        else:
            rows = connection.execute(
                """
                SELECT * FROM client_previews
                WHERE is_active = 1
                ORDER BY created_at DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]


def get_client_preview(preview_id):
    init_database()
    with db_connect() as connection:
        row = connection.execute(
            """
            SELECT * FROM client_previews
            WHERE id = ?
            """,
            (preview_id,),
        ).fetchone()

    return dict(row) if row else None


def update_client_preview(preview_id, fields):
    business_name = first(fields, "business_name") or "Unnamed Business"
    demo_link = first(fields, "demo_link")
    loom_link = first(fields, "loom_link")
    notes = first(fields, "notes")

    if not demo_link:
        raise ValueError("Client preview link is required.")

    init_database()
    with db_connect() as connection:
        connection.execute(
            """
            UPDATE client_previews
            SET business_name = ?,
                demo_link = ?,
                loom_link = ?,
                notes = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                business_name,
                demo_link,
                loom_link,
                notes,
                datetime.now().isoformat(timespec="seconds"),
                preview_id,
            ),
        )


def deactivate_client_preview(preview_id):
    init_database()
    with db_connect() as connection:
        connection.execute(
            """
            UPDATE client_previews
            SET is_active = 0, updated_at = ?
            WHERE id = ?
            """,
            (datetime.now().isoformat(timespec="seconds"), preview_id),
        )



def delete_client_preview(preview_id):
    init_database()
    with db_connect() as connection:
        connection.execute(
            """
            DELETE FROM client_previews
            WHERE id = ?
            """,
            (preview_id,),
        )




def normalize_prospect_text(value):
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def normalize_phone(value):
    return re.sub(r"\D+", "", value or "")


def normalize_website(value):
    value = (value or "").strip().lower()
    value = value.replace("https://", "").replace("http://", "").replace("www.", "")
    return value.rstrip("/")


def prospect_already_exists(business_name, website="", phone="", city_state=""):
    init_database()

    incoming_name = normalize_prospect_text(business_name)
    incoming_website = normalize_website(website)
    incoming_phone = normalize_phone(phone)
    incoming_city = normalize_prospect_text((city_state or "").split(",")[0])

    with db_connect() as connection:
        rows = connection.execute(
            "SELECT id, business_name, website, phone, city_state FROM prospects"
        ).fetchall()

    for row in rows:
        existing_name = normalize_prospect_text(row["business_name"])
        existing_website = normalize_website(row["website"])
        existing_phone = normalize_phone(row["phone"])
        existing_city = normalize_prospect_text((row["city_state"] or "").split(",")[0])

        if incoming_phone and existing_phone and incoming_phone == existing_phone:
            return True

        if incoming_website and existing_website and incoming_website == existing_website:
            return True

        same_name = incoming_name and existing_name and incoming_name == existing_name
        same_city = incoming_city and existing_city and incoming_city == existing_city

        if same_name and same_city:
            return True

        if same_name and not incoming_city:
            return True

    return False


def search_google_places_text(search_query, max_results=10):
    api_key = os.getenv("GOOGLE_PLACES_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Missing GOOGLE_PLACES_API_KEY. Add it in Render environment variables, then redeploy.")

    try:
        max_results = int(max_results or 10)
    except ValueError:
        max_results = 10

    max_results = max(1, min(20, max_results))

    endpoint = "https://places.googleapis.com/v1/places:searchText"
    payload = json.dumps(
        {
            "textQuery": search_query,
            "maxResultCount": max_results,
        }
    ).encode("utf-8")

    field_mask = ",".join(
        [
            "places.id",
            "places.displayName",
            "places.formattedAddress",
            "places.nationalPhoneNumber",
            "places.websiteUri",
            "places.googleMapsUri",
            "places.rating",
            "places.userRatingCount",
            "places.businessStatus",
        ]
    )

    request = urllib.request.Request(
        endpoint,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": field_mask,
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Google Places search failed: {error.code} {details}") from error
    except Exception as error:
        raise RuntimeError(f"Google Places search failed: {error}") from error

    return data.get("places", [])


def analyze_website_quality(website_url):
    result = {
        "has_website": bool(website_url),
        "loads": False,
        "uses_https": False,
        "has_mobile_viewport": False,
        "has_contact_signal": False,
        "has_booking_signal": False,
        "has_form_signal": False,
        "thin_content": False,
        "issues": [],
    }

    if not website_url:
        result["issues"].append("No website listed")
        return result

    result["uses_https"] = website_url.lower().startswith("https://")
    if not result["uses_https"]:
        result["issues"].append("Website is not using HTTPS")

    try:
        request = urllib.request.Request(
            website_url,
            headers={
                "User-Agent": "Mozilla/5.0 HouseOfVisualsProspectReview/1.0"
            },
        )
        with urllib.request.urlopen(request, timeout=8) as response:
            html = response.read(250000).decode("utf-8", errors="ignore").lower()
            result["loads"] = True
    except Exception as error:
        result["issues"].append(f"Website did not load cleanly: {error}")
        return result

    if 'name="viewport"' in html or "name='viewport'" in html:
        result["has_mobile_viewport"] = True
    else:
        result["issues"].append("No mobile viewport found")

    contact_terms = ["contact", "call", "phone", "email", "visit us", "location"]
    booking_terms = ["book", "booking", "appointment", "schedule", "reserve"]
    form_terms = ["<form", "request", "inquiry", "quote", "consultation"]

    result["has_contact_signal"] = any(term in html for term in contact_terms)
    result["has_booking_signal"] = any(term in html for term in booking_terms)
    result["has_form_signal"] = any(term in html for term in form_terms)

    if not result["has_contact_signal"]:
        result["issues"].append("No clear contact signal found")

    if not result["has_booking_signal"]:
        result["issues"].append("No clear booking/appointment signal found")

    if not result["has_form_signal"]:
        result["issues"].append("No clear form/inquiry signal found")

    visible_text_estimate = re.sub(r"<[^>]+>", " ", html)
    visible_text_estimate = re.sub(r"\s+", " ", visible_text_estimate).strip()

    if len(visible_text_estimate) < 900:
        result["thin_content"] = True
        result["issues"].append("Website may have thin or limited content")

    return result



def place_to_prospect_fields(place, industry, suggested_offer, recommended_demo):
    business_name = (place.get("displayName") or {}).get("text", "").strip()
    city_state = place.get("formattedAddress", "").strip()
    website = place.get("websiteUri", "").strip()
    phone = place.get("nationalPhoneNumber", "").strip()
    google_maps = place.get("googleMapsUri", "").strip()
    rating = place.get("rating", "")
    review_count = place.get("userRatingCount", "")
    business_status = place.get("businessStatus", "")

    website_check = analyze_website_quality(website)
    has_website = bool(website)
    website_issues = website_check.get("issues", [])

    lead_score = 2
    why_reasons = []

    if not has_website:
        lead_score += 6
        why_reasons.append("No website listed")
    else:
        if not website_check.get("loads"):
            lead_score += 6
            why_reasons.append("Website did not load cleanly")
        if not website_check.get("uses_https"):
            lead_score += 1
            why_reasons.append("Website may not be using HTTPS")
        if not website_check.get("has_mobile_viewport"):
            lead_score += 2
            why_reasons.append("No mobile viewport detected")
        if not website_check.get("has_booking_signal"):
            lead_score += 2
            why_reasons.append("No clear booking or appointment signal detected")
        if not website_check.get("has_form_signal"):
            lead_score += 1
            why_reasons.append("No clear form or inquiry signal detected")
        if website_check.get("thin_content"):
            lead_score += 1
            why_reasons.append("Website may have thin or limited content")

    if phone:
        lead_score += 1
        why_reasons.append("Phone number listed")

    if rating or review_count:
        lead_score += 1
        why_reasons.append("Has Google review activity")

    if recommended_demo:
        lead_score += 1
        why_reasons.append(f"Good fit for {recommended_demo}")

    lead_score = max(0, min(10, lead_score))

    if lead_score >= 8:
        review_priority = "High Priority"
    elif lead_score >= 6:
        review_priority = "Medium Priority"
    elif lead_score >= 4:
        review_priority = "Low Priority"
    else:
        review_priority = "Manual Review"

    if not has_website:
        website_status = "No website listed - high priority"
        potential_need = "No website listed. Strong opportunity for a branded website, inquiry form, booking/contact flow, and lead capture system."
    elif not website_check.get("loads"):
        website_status = "Website did not load cleanly - high priority"
        potential_need = "Website is listed but did not load cleanly during review. Strong opportunity for a refreshed website and lead capture system."
    elif lead_score >= 7:
        website_status = "Website listed but likely needs improvement"
        potential_need = "Website is listed, but basic review suggests possible gaps in mobile setup, booking/contact flow, inquiry capture, or content clarity."
    else:
        website_status = "Website listed - lower priority, manual review"
        potential_need = "Website is listed. Manually review design quality, booking/inquiry process, lead capture, service clarity, and overall user experience."

    if not why_reasons:
        why_reasons.append("Imported for manual review")

    notes = [
        "Imported by Google Places Research Bot.",
        f"Google Maps: {google_maps or '-'}",
        f"Rating: {rating or '-'}",
        f"Review Count: {review_count or '-'}",
        f"Business Status: {business_status or '-'}",
        f"Website Review Issues: {'; '.join(website_issues) if website_issues else 'No major technical issues found in basic scan'}",
        "Priority logic: no website, broken website, weak booking/contact signals, or thin content increase lead score.",
    ]

    return {
        "business_name": [business_name or "Unnamed Business"],
        "contact_name": [""],
        "industry": [industry],
        "city_state": [city_state],
        "website": [website],
        "instagram": [""],
        "facebook": [""],
        "email": [""],
        "phone": [phone],
        "website_status": [website_status],
        "potential_need": [potential_need],
        "suggested_offer": [suggested_offer],
        "recommended_demo": [recommended_demo],
        "lead_score": [str(lead_score)],
        "review_priority": [review_priority],
        "why_this_prospect": ["\n".join(why_reasons)],
        "status": ["New Prospect"],
        "notes": ["\n".join(notes)],
        "last_contacted": [""],
        "next_follow_up": [""],
    }


def import_places_as_prospects(
    places,
    industry,
    suggested_offer,
    recommended_demo,
    target_mode="needs_help",
    min_score=0,
):
    imported = 0
    skipped = 0
    errors = []

    try:
        min_score = int(min_score or 0)
    except ValueError:
        min_score = 0

    min_score = max(0, min(10, min_score))

    for place in places:
        fields = place_to_prospect_fields(place, industry, suggested_offer, recommended_demo)

        business_name = first(fields, "business_name")
        website = first(fields, "website")
        phone = first(fields, "phone")
        website_status = first(fields, "website_status").lower()
        score = int(first(fields, "lead_score") or 0)

        if target_mode == "no_website" and website:
            skipped += 1
            continue

        if target_mode == "needs_help":
            looks_like_need = (
                "no website" in website_status
                or "did not load" in website_status
                or "needs improvement" in website_status
                or score >= min_score
            )
            if not looks_like_need:
                skipped += 1
                continue

        if score < min_score:
            skipped += 1
            continue

        if prospect_already_exists(business_name, website, phone, first(fields, "city_state")):
            skipped += 1
            continue

        try:
            create_prospect(fields)
            imported += 1
        except Exception as error:
            skipped += 1
            errors.append(f"{business_name}: {error}")

    return {"imported": imported, "skipped": skipped, "errors": errors[:10]}


def import_prospects_from_csv(csv_text):
    init_database()
    imported = 0
    skipped = 0
    errors = []

    aliases = {
        "business": "business_name",
        "business name": "business_name",
        "name": "business_name",
        "contact": "contact_name",
        "contact name": "contact_name",
        "owner": "contact_name",
        "city": "city_state",
        "location": "city_state",
        "website status": "website_status",
        "need": "potential_need",
        "potential need": "potential_need",
        "offer": "suggested_offer",
        "suggested offer": "suggested_offer",
        "demo": "recommended_demo",
        "recommended demo": "recommended_demo",
        "score": "lead_score",
        "lead score": "lead_score",
        "follow up": "next_follow_up",
        "follow-up": "next_follow_up",
        "next follow up": "next_follow_up",
        "next_followup": "next_follow_up",
    }

    required_fields = ["business_name"]

    reader = csv.DictReader(csv_text.splitlines())
    if not reader.fieldnames:
        return {"imported": 0, "skipped": 0, "errors": ["CSV needs a header row."]}

    for row_number, row in enumerate(reader, start=2):
        normalized = {}
        for key, value in row.items():
            if key is None:
                continue
            clean_key = key.strip().lower()
            mapped_key = aliases.get(clean_key, clean_key.replace(" ", "_").replace("-", "_"))
            normalized[mapped_key] = [str(value or "").strip()]

        if not any(first(normalized, field) for field in required_fields):
            skipped += 1
            errors.append(f"Row {row_number}: missing business_name.")
            continue

        try:
            create_prospect(normalized)
            imported += 1
        except Exception as error:
            skipped += 1
            errors.append(f"Row {row_number}: {error}")

    return {"imported": imported, "skipped": skipped, "errors": errors[:10]}


def get_industry_message_profile(industry_raw):
    industry = (industry_raw or "local service").strip().lower()

    profiles = {
        "barber": {
            "label": "barber shops",
            "client_action": "book appointments, view services, and find the right cut or grooming service",
            "value": "make it easier for new clients to book, understand your services, and come back again",
        },
        "barbers": {
            "label": "barber shops",
            "client_action": "book appointments, view services, and find the right cut or grooming service",
            "value": "make it easier for new clients to book, understand your services, and come back again",
        },
        "barbershop": {
            "label": "barber shops",
            "client_action": "book appointments, view services, and find the right cut or grooming service",
            "value": "make it easier for new clients to book, understand your services, and come back again",
        },
        "salon": {
            "label": "salons",
            "client_action": "view services, request appointments, and choose the right stylist or beauty service",
            "value": "turn social media interest and website visits into real appointment requests",
        },
        "salons": {
            "label": "salons",
            "client_action": "view services, request appointments, and choose the right stylist or beauty service",
            "value": "turn social media interest and website visits into real appointment requests",
        },
        "realtor": {
            "label": "real estate professionals",
            "client_action": "view listings, request consultations, and learn how you help buyers and sellers",
            "value": "capture buyer and seller inquiries instead of relying only on social media or referrals",
        },
        "realtors": {
            "label": "real estate professionals",
            "client_action": "view listings, request consultations, and learn how you help buyers and sellers",
            "value": "capture buyer and seller inquiries instead of relying only on social media or referrals",
        },
        "contractor": {
            "label": "contractors",
            "client_action": "review services, request estimates, and see past work",
            "value": "turn website visitors into quote requests with a clearer project inquiry flow",
        },
        "contractors": {
            "label": "contractors",
            "client_action": "review services, request estimates, and see past work",
            "value": "turn website visitors into quote requests with a clearer project inquiry flow",
        },
        "cleaning": {
            "label": "cleaning businesses",
            "client_action": "request quotes, review services, and schedule cleaning inquiries",
            "value": "make it easier for residential or commercial clients to request service",
        },
        "restaurant": {
            "label": "restaurants and food businesses",
            "client_action": "view menus, place inquiries, book catering, or find location details quickly",
            "value": "make the customer experience smoother from search to visit or order",
        },
        "restaurants": {
            "label": "restaurants and food businesses",
            "client_action": "view menus, place inquiries, book catering, or find location details quickly",
            "value": "make the customer experience smoother from search to visit or order",
        },
        "health": {
            "label": "health and wellness businesses",
            "client_action": "learn about services, request appointments, and complete intake steps",
            "value": "make the patient or client inquiry process feel clear, trustworthy, and easy",
        },
        "wellness": {
            "label": "health and wellness businesses",
            "client_action": "learn about services, request appointments, and complete intake steps",
            "value": "make the patient or client inquiry process feel clear, trustworthy, and easy",
        },
        "event": {
            "label": "event spaces and venues",
            "client_action": "view the space, check services, and submit booking inquiries",
            "value": "capture event inquiries and make it easier for people to request dates or details",
        },
        "event space": {
            "label": "event spaces and venues",
            "client_action": "view the space, check services, and submit booking inquiries",
            "value": "capture event inquiries and make it easier for people to request dates or details",
        },
    }

    if industry in profiles:
        return profiles[industry]

    for key, profile in profiles.items():
        if key in industry:
            return profile

    return {
        "label": f"{industry} businesses",
        "client_action": "view services, submit inquiries, and understand the next step",
        "value": "turn more online visitors into real inquiries",
    }


def generate_outreach_messages(prospect):
    business_name = prospect.get("business_name") or "your business"
    contact_name = prospect.get("contact_name") or ""
    industry_raw = (prospect.get("industry") or "local business").strip().lower()
    recommended_demo = prospect.get("recommended_demo") or "industry demo"

    profile = get_industry_message_profile(industry_raw)
    industry_label = profile["label"]

    greeting_name = contact_name.split()[0] if contact_name else "there"

    instagram_dm = f"""Hi {greeting_name}! We came across {business_name} while researching local businesses in the RDU area and wanted to introduce ourselves.

We’re the husband-and-wife team behind House of Visuals. We help small businesses with website design, branding, content creation, booking and inquiry flows, and lead-management systems.

We have a polished {recommended_demo} created for {industry_label} that shows what a stronger online experience could look like. We’d be happy to send it over for you to review—no pressure at all.

If you like the direction, the next step would be completing our short project inquiry form. From there, we can create a personalized demo for {business_name} and walk through it together on a demo call.

You can also learn more about us and view some of our past work at houseofvisualsco.com.

Would you be open to seeing the industry demo?"""

    email_message = f"""Hi {greeting_name},

We recently came across {business_name} while researching local businesses in the RDU area and wanted to introduce ourselves.

We’re the husband-and-wife team behind House of Visuals, a local creative agency helping small businesses improve how they show up online. Our services include website design and redesign, branding, content creation, booking and inquiry flows, marketing materials, and lead-management systems.

We have a polished {recommended_demo} created for {industry_label} that shows what a stronger online experience could look like. We’d be happy to send it over for you to review—there’s no obligation or pressure.

If you like the direction, the next step would be completing our short project inquiry form. From there, we can create a personalized demo for {business_name} and walk through it together on a demo call.

You can visit houseofvisualsco.com to learn more about our services and view examples of work we’ve completed for other businesses.

Would you be open to seeing the industry demo?

Best,
The House of Visuals Team"""

    follow_up = f"""Hi {greeting_name}, just following up on the message we sent about {business_name}.

We’d still be happy to share the {recommended_demo} we mentioned. It’s a visual example of how a business in your industry could present its services and customer inquiry process in a more polished and organized way.

If you like the direction, you can complete our short project inquiry form and we can create a personalized demo for {business_name}.

You can also learn more about us and view some of our previous work at houseofvisualsco.com.

No pressure at all—just let us know if you’d like us to send the industry demo over.

— The House of Visuals Team"""

    return {
        "instagram_dm": instagram_dm,
        "email_message": email_message,
        "follow_up": follow_up,
    }


def generate_outreach_message(prospect):
    return generate_outreach_messages(prospect)["instagram_dm"]


DEMO_OPTIONS = [
    "Salon Demo",
    "Realtor Demo",
    "Health & Wellness Demo",
    "Ecommerce Demo",
    "Restaurant / Food Demo",
    "Event Space Demo",
    "Contractor Demo",
    "Cleaning Business Demo",
    "Content Creation Demo",
    "Custom Business Demo",
]

OFFER_OPTIONS = [
    "Website + lead system",
    "Website redesign",
    "New website build",
    "Booking/inquiry flow",
    "Lead capture dashboard",
    "Content creation",
    "Brand refresh",
    "SEO/local visibility review",
    "Google profile review",
    "Social media content system",
]


def many_offer_values(fields):
    selected = many(fields, "suggested_offer[]")
    if selected:
        return ", ".join(selected)
    return first(fields, "suggested_offer") or "Website + lead system"



class SiteHandler(SimpleHTTPRequestHandler):

    def _send_json(self, payload, status=200):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_html(self, html, status=200):
        data = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _admin_session_signature(self):
        token = os.getenv("HOV_ADMIN_TOKEN", "")
        if not token:
            return ""
        return hmac.new(token.encode("utf-8"), b"house-of-visuals-admin", hashlib.sha256).hexdigest()

    def _get_cookie(self, name):
        cookie_header = self.headers.get("Cookie", "")
        for part in cookie_header.split(";"):
            if "=" not in part:
                continue
            key, value = part.strip().split("=", 1)
            if key == name:
                return value
        return ""

    def _admin_allowed(self):
        token = os.getenv("HOV_ADMIN_TOKEN", "")
        is_local_request = self.client_address[0] in {"127.0.0.1", "::1", "localhost"}
        if not token:
            return is_local_request

        query = parse_qs(self.path.split("?", 1)[1] if "?" in self.path else "")
        header_token = self.headers.get("X-Admin-Token", "")
        cookie_session = self._get_cookie("hov_admin_session")

        if header_token == token or token in query.get("token", []):
            return True

        return hmac.compare_digest(cookie_session, self._admin_session_signature())

    def _send_admin_login_required(self, message="Enter your admin password to continue.", status=401):
        next_path = escape(self.path or "/admin")
        error_html = f"<p class='error'>{escape(message)}</p>" if message else ""
        self._send_html(
            f"""
            <!doctype html>
            <html lang="en">
              <head>
                <meta charset="utf-8" />
                <meta name="viewport" content="width=device-width, initial-scale=1" />
                <meta name="robots" content="noindex, nofollow" />
                <title>Admin Login | House of Visuals</title>
                <style>
                  * {{ box-sizing: border-box; }}
                  body {{
                    margin: 0;
                    min-height: 100vh;
                    display: grid;
                    place-items: center;
                    font-family: Manrope, Inter, system-ui, sans-serif;
                    color: #142119;
                    background: linear-gradient(160deg, #f8f4eb, #eef7f0);
                    padding: 1rem;
                  }}
                  .login-card {{
                    width: min(100%, 440px);
                    border: 1px solid rgba(15, 74, 51, 0.16);
                    border-radius: 22px;
                    background: rgba(255, 255, 255, 0.96);
                    box-shadow: 0 18px 40px rgba(13, 32, 23, 0.12);
                    padding: 1.4rem;
                  }}
                  .brand {{
                    border-radius: 18px;
                    background: linear-gradient(145deg, #0b130f, #123b2b);
                    color: #f7f1e4;
                    padding: 1.2rem;
                    margin-bottom: 1rem;
                  }}
                  .brand p {{
                    margin: 0 0 0.35rem;
                    color: #ead7a7;
                    font-weight: 800;
                  }}
                  h1 {{
                    margin: 0;
                    font-family: Georgia, serif;
                    font-size: clamp(2rem, 8vw, 3rem);
                    line-height: 1;
                  }}
                  label {{
                    display: grid;
                    gap: 0.45rem;
                    color: #0f4a33;
                    font-weight: 900;
                    margin-bottom: 0.9rem;
                  }}
                  input {{
                    width: 100%;
                    border: 1px solid rgba(15, 74, 51, 0.22);
                    border-radius: 14px;
                    padding: 0.85rem;
                    font: inherit;
                  }}
                  button {{
                    width: 100%;
                    border: 0;
                    border-radius: 999px;
                    background: linear-gradient(135deg, #1f7a57, #29a16f);
                    color: #fff;
                    font-weight: 900;
                    padding: 0.9rem 1rem;
                    cursor: pointer;
                  }}
                  .help {{
                    color: #516257;
                    font-size: 0.92rem;
                    margin: 0.8rem 0 0;
                  }}
                  .error {{
                    color: #8a2d1f;
                    background: #fff1ed;
                    border: 1px solid #f0b5a8;
                    border-radius: 12px;
                    padding: 0.7rem;
                    margin: 0 0 0.9rem;
                    font-weight: 800;
                  }}
      
              /* Final admin button polish */
              .admin-nav {{
                display: flex !important;
                align-items: center !important;
                justify-content: flex-end !important;
                gap: 0.55rem !important;
                flex-wrap: wrap !important;
              }}

              .btn,
              .btn-small,
              .admin-nav a,
              .quick-actions a {{
                display: inline-flex !important;
                align-items: center !important;
                justify-content: center !important;
                min-height: 40px !important;
                padding: 0.65rem 0.95rem !important;
                border-radius: 999px !important;
                font-weight: 900 !important;
                font-size: 0.9rem !important;
                line-height: 1 !important;
                text-decoration: none !important;
                white-space: nowrap !important;
                cursor: pointer !important;
                border: 1px solid rgba(15, 74, 51, 0.16) !important;
                box-shadow: 0 8px 14px rgba(13, 32, 23, 0.06) !important;
                margin: 0 !important;
              }}

              .btn {{
                background: linear-gradient(135deg, #1f7a57, #29a16f) !important;
                color: #fff !important;
                border-color: transparent !important;
              }}

              .btn-small,
              .admin-nav a,
              .quick-actions a:not(.btn) {{
                background: #fffdf7 !important;
                color: var(--green) !important;
              }}

              .admin-nav a[href="/admin/logout"] {{
                background: #fff1ed !important;
                color: #8a2d1f !important;
                border-color: rgba(138, 45, 31, 0.22) !important;
              }}

              .quick-actions {{
                display: flex !important;
                align-items: center !important;
                gap: 0.55rem !important;
                flex-wrap: wrap !important;
              }}

              .hero .quick-actions {{
                margin-top: 1rem !important;
              }}

              .panel-head {{
                align-items: center !important;
              }}

              @media (max-width: 700px) {{
                .admin-nav,
                .quick-actions {{
                  justify-content: stretch !important;
                }}

                .btn,
                .btn-small,
                .admin-nav a,
                .quick-actions a {{
                  width: 100% !important;
                }}
              }}

          </style>
              </head>
              <body>
                <main class="login-card">
                  <section class="brand">
                    <p>House of Visuals Admin</p>
                    <h1>Admin Login</h1>
                  </section>

                  {error_html}

                  <form method="post" action="/admin/login">
                    <input type="hidden" name="next" value="{next_path}" />
                    <label>Password
                      <input type="password" name="password" autocomplete="current-password" required autofocus />
                    </label>
                    <button type="submit">Open Admin Dashboard</button>
                  </form>

                  <p class="help">Use your private admin password from Render: <strong>HOV_ADMIN_TOKEN</strong>.</p>
                </main>
              </body>
            </html>
            """,
            status=status,
        )

    def _send_csv(self, filename, headers, rows):
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(headers)
        writer.writerows(rows)

        data = output.getvalue().encode("utf-8-sig")
        self.send_response(200)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _export_leads_csv(self, completed_only=False):
        leads = get_leads()

        if completed_only:
            leads = [lead for lead in leads if lead.get("status") == "Completed"]
            filename = "completed-projects.csv"
        else:
            leads = [lead for lead in leads if lead.get("status") != "Completed"]
            filename = "active-leads.csv"

        headers = [
            "id",
            "submitted_at",
            "updated_at",
            "status",
            "full_name",
            "business_name",
            "email",
            "phone",
            "website_social",
            "project_types",
            "timeline",
            "budget",
            "referral_source",
            "internal_notes",
        ]

        rows = []
        for lead in leads:
            rows.append([
                lead.get("id", ""),
                lead.get("submitted_at", ""),
                lead.get("updated_at", ""),
                lead.get("status", ""),
                lead.get("full_name", ""),
                lead.get("business_name", ""),
                lead.get("email", ""),
                lead.get("phone", ""),
                lead.get("website_social", ""),
                ", ".join(lead.get("project_types") or []),
                lead.get("timeline", ""),
                lead.get("budget", ""),
                lead.get("referral_source", ""),
                lead.get("internal_notes", ""),
            ])

        self._send_csv(filename, headers, rows)

    def _export_prospects_csv(self):
        prospects = get_prospects()

        headers = [
            "id",
            "added_at",
            "updated_at",
            "business_name",
            "contact_name",
            "industry",
            "city_state",
            "website",
            "instagram",
            "facebook",
            "email",
            "phone",
            "website_status",
            "potential_need",
            "suggested_offer",
            "recommended_demo",
            "lead_score",
            "review_priority",
            "why_this_prospect",
            "status",
            "last_contacted",
            "next_follow_up",
            "notes",
        ]

        rows = []
        for prospect in prospects:
            rows.append([
                prospect.get("id", ""),
                prospect.get("added_at", ""),
                prospect.get("updated_at", ""),
                prospect.get("business_name", ""),
                prospect.get("contact_name", ""),
                prospect.get("industry", ""),
                prospect.get("city_state", ""),
                prospect.get("website", ""),
                prospect.get("instagram", ""),
                prospect.get("facebook", ""),
                prospect.get("email", ""),
                prospect.get("phone", ""),
                prospect.get("website_status", ""),
                prospect.get("potential_need", ""),
                prospect.get("suggested_offer", ""),
                prospect.get("recommended_demo", ""),
                prospect.get("lead_score", ""),
                prospect.get("review_priority", ""),
                prospect.get("why_this_prospect", ""),
                prospect.get("status", ""),
                prospect.get("last_contacted", ""),
                prospect.get("next_follow_up", ""),
                prospect.get("notes", ""),
            ])

        self._send_csv("prospects.csv", headers, rows)

    def _render_completed_projects(self):
        completed_leads = [lead for lead in get_leads() if lead.get("status") == "Completed"]

        rows = []
        for lead in completed_leads:
            rows.append(
                f"""
                <tr>
                  <td><a href="/admin/leads/{lead['id']}">#{lead['id']}</a></td>
                  <td>{escape(lead.get('updated_at') or '')}</td>
                  <td>
                    <strong>{escape(lead.get('full_name') or 'Completed Project')}</strong>
                    <span class="mobile-muted">{escape(lead.get('email') or '')}</span>
                  </td>
                  <td>{escape(lead.get('business_name') or '-')}</td>
                  <td>{escape(lead.get('email') or '-')}</td>
                  <td>{escape(lead.get('phone') or '-')}</td>
                  <td>{escape(', '.join(lead.get('project_types') or []) or '-')}</td>
                  <td>{escape(lead.get('budget') or '-')}</td>
                  <td><a class="btn-small" href="/admin/leads/{lead['id']}">View</a></td>
                </tr>
                """
            )

        empty_state = """
            <tr>
              <td colspan="9">
                <div class="empty-state">
                  <h3>No completed projects yet.</h3>
                  <p>When you change a lead status to Completed, it will move here automatically.</p>
                  <a class="btn-small" href="/admin">Back to Leads</a>
                </div>
              </td>
            </tr>
        """

        return self._admin_shell(
            "Completed Projects",
            f"""
            <section class="hero">
              <p>House of Visuals Admin</p>
              <h1>Completed Projects</h1>
              <a class="btn" href="/admin/completed/export">Export Completed CSV</a>
            </section>

            <section class="stats stats-four">
              <article><strong>{len(completed_leads)}</strong><span>Completed Projects</span></article>
              <article><strong>-</strong><span>Archived from Leads</span></article>
              <article><strong>-</strong><span>Kept for Records</span></article>
              <article><strong>-</strong><span>Export Ready</span></article>
            </section>

            <section class="panel">
              <div class="panel-head">
                <div>
                  <h2>Completed Project Log</h2>
                  <p>These leads are hidden from the active dashboard once marked Completed.</p>
                </div>
                <a class="btn-small" href="/admin">View Active Leads</a>
              </div>

              <div class="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Completed / Updated</th>
                      <th>Name</th>
                      <th>Business</th>
                      <th>Email</th>
                      <th>Phone</th>
                      <th>Service</th>
                      <th>Budget</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>{''.join(rows) if rows else empty_state}</tbody>
                </table>
              </div>
            </section>
            """,
        )

    def _render_research_helper(self, result=None, values=None):
        values = values or {}
        query_params = parse_qs(self.path.split("?", 1)[1] if "?" in self.path else "")

        def field_value(name, default=""):
            if values and name in values:
                return first(values, name)
            return query_params.get(name, [default])[0].strip()

        industry = field_value("industry")
        location = field_value("location")
        recommended_demo = field_value("recommended_demo")
        suggested_offer = many_offer_values(values) if values else field_value("suggested_offer", "Website + lead system")
        max_results = field_value("max_results", "10")
        min_score = field_value("min_score", "7")
        target_mode = field_value("target_mode", "needs_help")
        search_query = field_value("search_query")

        search_phrase = search_query or " ".join(part for part in [industry, "in", location] if part).strip()
        encoded_search = quote_plus(search_phrase or "small businesses near me")
        encoded_instagram = quote_plus(f"site:instagram.com {industry} {location}".strip())
        encoded_website_search = quote_plus(f"{industry} {location} website contact booking".strip())

        maps_url = f"https://www.google.com/maps/search/?api=1&query={encoded_search}"
        google_url = f"https://www.google.com/search?q={encoded_website_search}"
        instagram_url = f"https://www.google.com/search?q={encoded_instagram}"

        csv_template = f"""business_name,contact_name,industry,city_state,website,instagram,email,phone,website_status,potential_need,suggested_offer,recommended_demo,lead_score,status,next_follow_up
Example Business,,{industry},{location},,,,,No website,Needs website/lead capture review,{suggested_offer},{recommended_demo},7,Needs Review,"""
        selected_offers = []
        if values:
            selected_offers = many(values, "suggested_offer[]")
            if not selected_offers and first(values, "suggested_offer"):
                selected_offers = [first(values, "suggested_offer")]
        elif suggested_offer:
            selected_offers = [offer.strip() for offer in suggested_offer.split(",") if offer.strip()]

        demo_options_html = "".join(
            f"<option value='{escape(option)}' {'selected' if recommended_demo == option else ''}>{escape(option)}</option>"
            for option in DEMO_OPTIONS
        )

        offer_options_html = "".join(
            f"""
            <label class='check-row'>
              <input type='checkbox' name='suggested_offer[]' value='{escape(option)}' {'checked' if option in selected_offers else ''} />
              <span>{escape(option)}</span>
              <strong>Select</strong>
            </label>
            """
            for option in OFFER_OPTIONS
        )


        result_html = ""
        if result:
            errors = "".join(f"<li>{escape(error)}</li>" for error in result.get("errors", []))
            result_html = f"""
            <section class="panel">
              <h2>Google Places Bot Results</h2>
              <p><strong>{result.get('imported', 0)}</strong> imported into Prospects. <strong>{result.get('skipped', 0)}</strong> skipped as duplicates or errors.</p>
              {f"<ul>{errors}</ul>" if errors else ""}
              <a class="btn-small" href="/admin/prospects">View Prospect Pipeline</a>
            </section>
            """

        extra_searches = [
            f"{industry} {location}",
            f"{industry} near {location}",
            f"best {industry} in {location}",
            f"{industry} {location} instagram",
            f"{industry} {location} no website",
        ]

        extra_links = "".join(
            f"<a class='btn-small' target='_blank' rel='noopener' href='https://www.google.com/search?q={quote_plus(item)}'>{escape(item)}</a>"
            for item in extra_searches
            if item.strip()
        )

        return self._admin_shell(
            "Research Bot",
            f"""
            <section class="hero detail-hero">
              <p>House of Visuals Client Finder</p>
              <h1>Research Bot</h1>
              <p>Use Google Places to find best-fit prospects, prioritizing businesses with no website or weak/outdated websites.</p>
            </section>

            {result_html}

            <section class="panel">
              <h2>Automatic Google Places Search - Best-Fit Prospects</h2>
              <form class="filters" method="post" action="/admin/research">
                <label>Search Query
                  <input name="search_query" value="{escape(search_query)}" placeholder="barbers in Durham NC" />
                </label>

                <label>Industry
                  <input name="industry" value="{escape(industry)}" placeholder="Barber, Salon, Realtor..." />
                </label>

                <label>Location
                  <input name="location" value="{escape(location)}" placeholder="Durham NC" />
                </label>

                <label>Max Results
                  <input type="number" min="1" max="20" name="max_results" value="{escape(max_results)}" />
                </label>

                <label>Minimum Lead Score
                  <input type="number" min="0" max="10" name="min_score" value="{escape(min_score)}" />
                </label>

                <label>Recommended Demo
                  <select name="recommended_demo">
                    <option value="">Choose a demo</option>
                    {demo_options_html}
                  </select>
                </label>

                <label>Suggested Offers
                  <details class="multi-dropdown">
                    <summary>Choose one or more offers</summary>
                    <div class="multi-dropdown-menu">
                      {offer_options_html}
                    </div>
                  </details>
                </label>

                <label>Target Mode
                  <select name="target_mode">
                    <option value="needs_help" {'selected' if target_mode == 'needs_help' else ''}>No website OR weak/outdated website</option>
                    <option value="no_website" {'selected' if target_mode == 'no_website' else ''}>Only businesses with no website listed</option>
                    <option value="all_scored" {'selected' if target_mode == 'all_scored' else ''}>All businesses, scored by need</option>
                  </select>
                </label>

                <button class="btn" type="submit">Find + Import Best-Fit Prospects</button>
              </form>
            </section>

            <section class="panel">
              <h2>Free Research Links</h2>
              <p>Use these if you want to manually double-check results or collect more prospects for CSV import.</p>
              <div class="quick-actions">
                <a class="btn-small" target="_blank" rel="noopener" href="{maps_url}">Open Google Maps Search</a>
                <a class="btn-small" target="_blank" rel="noopener" href="{google_url}">Open Google Search</a>
                <a class="btn-small" target="_blank" rel="noopener" href="{instagram_url}">Open Instagram Search</a>
                <a class="btn-small" href="/admin/prospects/import">Go to Import Prospects</a>
              </div>
            </section>

            <section class="panel">
              <h2>Extra Search Ideas</h2>
              <div class="quick-actions">{extra_links}</div>
            </section>

            <section class="panel">
              <h2>CSV Starter Template</h2>
              <textarea class="outreach-copy" rows="7" readonly>{escape(csv_template)}</textarea>
              <div class="quick-actions">
                <a class="btn-small" href="/admin/prospects/import">Open Import Page</a>
              </div>
            </section>
            """,
        )

    def _render_prospects_import(self, result=None):
        result_html = ""
        if result:
            errors = "".join(f"<li>{escape(error)}</li>" for error in result.get("errors", []))
            result_html = f"""
            <section class="panel">
              <h2>Import Results</h2>
              <p><strong>{result.get('imported', 0)}</strong> imported. <strong>{result.get('skipped', 0)}</strong> skipped.</p>
              {f"<ul>{errors}</ul>" if errors else ""}
              <a class="btn-small" href="/admin/prospects">View Prospects</a>
            </section>
            """

        sample_csv = """business_name,contact_name,industry,city_state,website,instagram,email,phone,website_status,potential_need,suggested_offer,recommended_demo,lead_score,status,next_follow_up
Glow Beauty Bar,Monica,Salon,Durham NC,,https://instagram.com/glowbeautybar,hello@example.com,919-000-0000,No website,Needs booking/inquiry system,Website + lead system,Salon Demo,8,Ready to Contact,2026-06-01"""

        return self._admin_shell(
            "Import Prospects",
            f"""
            <section class="hero detail-hero">
              <p><a href="/admin/prospects">← Back to Prospects</a></p>
              <h1>Import Prospects</h1>
              <p>Paste CSV data from your spreadsheet to add multiple businesses at once.</p>
            </section>

            {result_html}

            <section class="panel">
              <h2>Paste CSV</h2>
              <form method="post" action="/admin/prospects/import">
                <label>CSV Data
                  <textarea name="csv_data" rows="12" placeholder="{escape(sample_csv)}"></textarea>
                </label>
                <button class="btn" type="submit">Import Prospects</button>
              </form>
            </section>

            <section class="panel">
              <h2>Recommended Columns</h2>
              <p>Use these headers: <code>business_name, contact_name, industry, city_state, website, instagram, email, phone, website_status, potential_need, suggested_offer, recommended_demo, lead_score, status, next_follow_up</code></p>
            </section>
            """,
        )

    def _render_prospects_dashboard(self):
        prospects = get_prospects()

        query_params = parse_qs(self.path.split("?", 1)[1] if "?" in self.path else "")
        selected_status = query_params.get("status", [""])[0].strip()
        selected_industry = query_params.get("industry", [""])[0].strip()
        selected_priority = query_params.get("priority", [""])[0].strip()
        search_term = query_params.get("q", [""])[0].strip().lower()

        filtered_prospects = []
        for prospect in prospects:
            searchable_text = " ".join(
                [
                    str(prospect.get("business_name") or ""),
                    str(prospect.get("contact_name") or ""),
                    str(prospect.get("industry") or ""),
                    str(prospect.get("city_state") or ""),
                    str(prospect.get("website") or ""),
                    str(prospect.get("instagram") or ""),
                    str(prospect.get("email") or ""),
                    str(prospect.get("phone") or ""),
                    str(prospect.get("potential_need") or ""),
                    str(prospect.get("suggested_offer") or ""),
                    str(prospect.get("recommended_demo") or ""),
                ]
            ).lower()

            if selected_status and prospect.get("status") != selected_status:
                continue
            if selected_industry and prospect.get("industry") != selected_industry:
                continue
            if selected_priority and prospect.get("review_priority") != selected_priority:
                continue
            if search_term and search_term not in searchable_text:
                continue

            filtered_prospects.append(prospect)

        status_counts = {status: 0 for status in DEFAULT_PROSPECT_STATUSES}
        for prospect in prospects:
            status_counts[prospect["status"]] = status_counts.get(prospect["status"], 0) + 1

        industries = sorted({p.get("industry") for p in prospects if p.get("industry")})

        today = datetime.now().strftime("%Y-%m-%d")
        follow_up_due = sum(
            1 for prospect in prospects
            if prospect.get("next_follow_up") and prospect.get("next_follow_up") <= today
        )

        summary_cards = f"""
            <article><strong>{len(prospects)}</strong><span>Total Prospects</span></article>
            <article><strong>{status_counts.get('Ready to Contact', 0)}</strong><span>Ready to Contact</span></article>
            <article><strong>{follow_up_due}</strong><span>Follow-Up Due</span></article>
            <article><strong>{status_counts.get('Interested', 0)}</strong><span>Interested</span></article>
        """

        status_options = "<option value=''>All Statuses</option>" + "".join(
            f"<option value='{escape(status)}' {'selected' if selected_status == status else ''}>{escape(status)}</option>"
            for status in DEFAULT_PROSPECT_STATUSES
        )

        industry_options = "<option value=''>All Industries</option>" + "".join(
            f"<option value='{escape(industry)}' {'selected' if selected_industry == industry else ''}>{escape(industry)}</option>"
            for industry in industries
        )

        priority_options = "<option value=''>All Priorities</option>" + "".join(
            f"<option value='{escape(priority)}' {'selected' if selected_priority == priority else ''}>{escape(priority)}</option>"
            for priority in [
                "High Priority",
                "Medium Priority",
                "Low Priority",
                "Manual Review",
            ]
        )

        rows = []
        for prospect in filtered_prospects:
            row_class = "followup-due" if prospect.get("next_follow_up") and prospect.get("next_follow_up") <= today else ""
            priority_class = (prospect.get("review_priority") or "Manual Review").lower().replace(" ", "-")
            rows.append(
                f"""
                <tr class="{row_class}">
                  <td><a href="/admin/prospects/{prospect['id']}">#{prospect['id']}</a></td>
                  <td>
                    <strong>{escape(prospect.get('business_name') or 'Unnamed Business')}</strong>
                    <span class="mobile-muted">{escape(prospect.get('city_state') or '')}</span>
                  </td>
                  <td>{escape(prospect.get('industry') or '-')}</td>
                  <td>{escape(prospect.get('city_state') or '-')}</td>
                  <td>{escape(prospect.get('website_status') or '-')}</td>
                  <td>{escape(prospect.get('recommended_demo') or '-')}</td>
                  <td>{escape(prospect.get('next_follow_up') or '-')}</td>
                  <td><span class="priority-pill priority-{priority_class}">{escape(prospect.get('review_priority') or 'Manual Review')}</span></td>
                  <td><span class="score-pill">{escape(str(prospect.get('lead_score') or 0))}/10</span></td>
                  <td><span class="status">{escape(prospect.get('status') or 'New Prospect')}</span></td>
                  <td><a class="btn-small" href="/admin/prospects/{prospect['id']}">View</a></td>
                </tr>
                """
            )

        empty_state = """
            <tr>
              <td colspan="11">
                <div class="empty-state">
                  <h3>No prospects yet.</h3>
                  <p>Add a business you want to reach out to and start building your client-finding pipeline.</p>
                  <a class="btn-small" href="/admin/prospects/new">Add Prospect</a>
                </div>
              </td>
            </tr>
        """

        return self._admin_shell(
            "Prospect Finder",
            f"""
            <section class="hero">
              <p>House of Visuals Client Finder</p>
              <h1>Prospect Pipeline</h1>
              <div class="quick-actions">
                <a class="btn" href="/admin/prospects/new">Add Prospect</a>
                <a class="btn-small" href="/admin/prospects/export">Export Prospects CSV</a>
              </div>
            </section>

            <section class="stats stats-four">{summary_cards}</section>

            <section class="panel">
              <div class="panel-head">
                <div>
                  <h2>Find + Filter Prospects</h2>
                  <p>Track businesses you may want to contact.</p>
                </div>
                <a class="btn-small" href="/admin/prospects">Reset</a>
              </div>

              <form class="filters" method="get" action="/admin/prospects">
                <label>Search
                  <input type="search" name="q" value="{escape(query_params.get('q', [''])[0])}" placeholder="Business, city, email, need, or demo" />
                </label>

                <label>Status
                  <select name="status">{status_options}</select>
                </label>

                <label>Industry
                  <select name="industry">{industry_options}</select>
                </label>

                <label>Priority
                  <select name="priority">{priority_options}</select>
                </label>

                <button class="btn" type="submit">Apply Filters</button>
              </form>
            </section>

            <section class="panel">
              <div class="panel-head">
                <div>
                  <h2>All Prospects</h2>
                  <p>Showing {len(filtered_prospects)} of {len(prospects)} possible clients</p>
                </div>
              </div>

              <div class="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Business</th>
                      <th>Industry</th>
                      <th>Location</th>
                      <th>Website Status</th>
                      <th>Recommended Demo</th>
                      <th>Next Follow-Up</th>
                      <th>Priority</th>
                      <th>Score</th>
                      <th>Status</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>{''.join(rows) if rows else empty_state}</tbody>
                </table>
              </div>
            </section>
            """,
        )

    def _render_prospect_form(self, prospect=None):
        prospect = prospect or {}
        is_edit = bool(prospect.get("id"))
        title = f"Prospect #{prospect['id']}" if is_edit else "Add Prospect"
        action = f"/admin/prospects/{prospect['id']}" if is_edit else "/admin/prospects/new"

        def value(name):
            return escape(str(prospect.get(name) or ""))

        status_options = "".join(
            f"<option value='{escape(status)}' {'selected' if prospect.get('status', 'New Prospect') == status else ''}>{escape(status)}</option>"
            for status in DEFAULT_PROSPECT_STATUSES
        )

        contact_method_options = "".join(
            f"<option value='{escape(method)}'>{escape(method)}</option>"
            for method in CONTACT_METHODS
        )

        outreach_history = (
            get_prospect_outreach_history(prospect["id"])
            if is_edit
            else []
        )

        outreach_history_rows = "".join(
            f"""
            <article class='message-card'>
              <h3>{escape(item.get('activity_type') or 'Contact')}</h3>
              <p><strong>{escape(item.get('contacted_at') or '')}</strong> via {escape(item.get('contact_method') or '')}</p>
              {f"<p>Next follow-up: {escape(item.get('next_follow_up') or '')}</p>" if item.get('next_follow_up') else "<p>No additional follow-up scheduled.</p>"}
              {f"<p>{escape(item.get('notes') or '')}</p>" if item.get('notes') else ""}
            </article>
            """
            for item in outreach_history
        )

        return self._admin_shell(
            title,
            f"""
            <section class="hero detail-hero">
              <p><a href="/admin/prospects">← Back to Prospects</a></p>
              <h1>{escape(title)}</h1>
              <p>{'Update this possible client.' if is_edit else 'Add a business you may want to contact.'}</p>

              {f"""
              <div class='quick-actions'>
                {f"<a class='btn-small' href='{escape(prospect.get('website') or '')}' target='_blank' rel='noopener'>Open Website</a>" if prospect.get('website') else ""}
                {f"<a class='btn-small' href='{escape(prospect.get('instagram') or '')}' target='_blank' rel='noopener'>Open Instagram</a>" if prospect.get('instagram') and str(prospect.get('instagram')).startswith('http') else ""}
              </div>
              """ if is_edit else ""}
            </section>

            <form method="post" action="{action}">
              <section class="detail-grid">
                <article class="panel">
                  <h2>Business Info</h2>

                  <label>Business Name
                    <input name="business_name" value="{value('business_name')}" required />
                  </label>

                  <label>Contact Name
                    <input name="contact_name" value="{value('contact_name')}" />
                  </label>

                  <label>Industry
                    <input name="industry" value="{value('industry')}" placeholder="Salon, Realtor, Contractor, etc." />
                  </label>

                  <label>City / State
                    <input name="city_state" value="{value('city_state')}" placeholder="Durham, NC" />
                  </label>

                  <label>Website
                    <input name="website" value="{value('website')}" placeholder="https://..." />
                  </label>

                  <label>Instagram
                    <input name="instagram" value="{value('instagram')}" placeholder="@businessname or link" />
                  </label>

                  <label>Facebook
                    <input name="facebook" value="{value('facebook')}" />
                  </label>

                  <label>Email
                    <input name="email" value="{value('email')}" />
                  </label>

                  <label>Phone
                    <input name="phone" value="{value('phone')}" />
                  </label>

                  {f"""
                  <div class='contact-actions-inline'>
                    <div class='panel-head'>
                      <div>
                        <h2>Contact Activity</h2>
                        <p>Record the first message or a follow-up without leaving this page.</p>
                      </div>
                    </div>

                    <article class='message-card'>
                      <h3>Mark as Contacted</h3>
                      <p>This sets the status to Contacted and schedules a follow-up in three days.</p>

                      <label>How did you contact them?
                        <select name='contact_method' form='mark-contacted-form' required>
                          <option value=''>Choose a method</option>
                          {contact_method_options}
                        </select>
                      </label>

                      <label>Optional Note
                        <textarea
                          name='contact_notes'
                          form='mark-contacted-form'
                          rows='3'
                          placeholder='Example: Sent the contractor demo through Instagram.'
                        ></textarea>
                      </label>

                      <button class='btn' type='submit' form='mark-contacted-form'>
                        Mark as Contacted
                      </button>
                    </article>

                    <article class='message-card'>
                      <h3>Log Final Follow-Up</h3>
                      <p>
                        Record the second and final message using
                        <strong>{escape(prospect.get('last_contact_method') or 'the original contact method')}</strong>.
                        A No Response review will be scheduled four days from today.
                      </p>

                      <button class='btn' type='submit' form='follow-up-form'>
                        Log Final Follow-Up
                      </button>
                    </article>

                    <article class='message-card'>
                      <h3>Mark as No Response</h3>
                      <p>Use this after the final follow-up window has passed and the prospect has not replied.</p>

                      <button
                        class='btn danger-btn'
                        type='submit'
                        form='no-response-form'
                        onclick="return window.confirm('Mark this prospect as No Response?');"
                      >
                        Mark as No Response
                      </button>
                    </article>
                  </div>
                  """ if is_edit else ""}
                </article>

                <article class="panel">
                  <h2>Opportunity Details</h2>

                  <label>Website Status
                    <input name="website_status" value="{value('website_status')}" placeholder="No website, outdated, weak contact form..." />
                  </label>

                  <label>Potential Need
                    <textarea name="potential_need" rows="5" placeholder="What do they seem to need?">{value('potential_need')}</textarea>
                  </label>

                  <label>Suggested Offer
                    <input name="suggested_offer" value="{value('suggested_offer')}" placeholder="Website, lead system, content, branding..." />
                  </label>

                  <label>Recommended Demo
                    <input name="recommended_demo" value="{value('recommended_demo')}" placeholder="Salon demo, realtor demo, contractor demo..." />
                  </label>

                  <div class="score-checklist">
                    <h3>Lead Score Checklist</h3>
                    <p>Check what applies. The score will auto-fill below.</p>

                    <label class="check-row">
                      <input type="checkbox" class="score-check" data-score="3" />
                      <span>No website or website is missing</span>
                      <strong>+3</strong>
                    </label>

                    <label class="check-row">
                      <input type="checkbox" class="score-check" data-score="2" />
                      <span>Website looks outdated or unfinished</span>
                      <strong>+2</strong>
                    </label>

                    <label class="check-row">
                      <input type="checkbox" class="score-check" data-score="2" />
                      <span>No clear contact form, booking button, or inquiry process</span>
                      <strong>+2</strong>
                    </label>

                    <label class="check-row">
                      <input type="checkbox" class="score-check" data-score="1" />
                      <span>Active Instagram, Facebook, or Google presence</span>
                      <strong>+1</strong>
                    </label>

                    <label class="check-row">
                      <input type="checkbox" class="score-check" data-score="1" />
                      <span>Good fit for one of your existing demos</span>
                      <strong>+1</strong>
                    </label>

                    <label class="check-row">
                      <input type="checkbox" class="score-check" data-score="1" />
                      <span>Business appears active and likely to invest</span>
                      <strong>+1</strong>
                    </label>
                  </div>

                  <label>Lead Score 0-10
                    <input id="lead_score" type="number" min="0" max="10" name="lead_score" value="{escape(str(prospect.get('lead_score', 0)))}" />
                  </label>

                  <label>Review Priority
                    <select name="review_priority">
                      <option value="High Priority" {'selected' if prospect.get('review_priority') == 'High Priority' else ''}>High Priority</option>
                      <option value="Medium Priority" {'selected' if prospect.get('review_priority') == 'Medium Priority' else ''}>Medium Priority</option>
                      <option value="Low Priority" {'selected' if prospect.get('review_priority') == 'Low Priority' else ''}>Low Priority</option>
                      <option value="Manual Review" {'selected' if prospect.get('review_priority', 'Manual Review') == 'Manual Review' else ''}>Manual Review</option>
                    </select>
                  </label>

                  <label>Why This Prospect
                    <textarea name="why_this_prospect" rows="5">{value('why_this_prospect')}</textarea>
                  </label>

                  <label>Status
                    <select name="status">{status_options}</select>
                  </label>

                  <label>Last Contacted
                    <input type="date" name="last_contacted" value="{value('last_contacted')}" />
                  </label>

                  <label>Next Follow-Up
                    <input type="date" name="next_follow_up" value="{value('next_follow_up')}" />
                  </label>

                  <label>Last Contact Method
                    <input value="{value('last_contact_method')}" placeholder="Not contacted yet" readonly />
                  </label>
                </article>
              </section>

              <section class="panel prospect-notes-panel">
                <div class="panel-head">
                  <div>
                    <h2>Notes</h2>
                    <p>Add internal details, reminders, or anything important about this prospect.</p>
                  </div>
                </div>

                <label>Internal Prospect Notes
                  <textarea name="notes" rows="6" placeholder="Add notes about the business, outreach, response, or next steps...">{value('notes')}</textarea>
                </label>

                <div class="quick-actions">
                  <button class="btn" type="submit">{'Save Prospect' if is_edit else 'Add Prospect'}</button>
                </div>
              </section>
            </form>

              {f"""
              <form
                id='mark-contacted-form'
                method='post'
                action='/admin/prospects/{prospect['id']}/mark-contacted'
              ></form>

              <form
                id='follow-up-form'
                method='post'
                action='/admin/prospects/{prospect['id']}/follow-up'
              ></form>

              <form
                id='no-response-form'
                method='post'
                action='/admin/prospects/{prospect['id']}/no-response'
              ></form>

              <section class='panel outreach-panel'>
                <div class='panel-head'>
                  <div>
                    <h2>Outreach History</h2>
                    <p>A record of how and when this prospect was contacted.</p>
                  </div>
                </div>

                <div class='message-grid'>
                  {outreach_history_rows if outreach_history_rows else "<article class='message-card'><p>No outreach has been recorded yet.</p></article>"}
                </div>
              </section>
              """ if is_edit else ""}

              {f"""
              <section class='panel outreach-panel'>
                <div class='panel-head'>
                  <div>
                    <h2>Outreach Message Generator</h2>
                    <p>Copy the best version for Instagram, email, or follow-up.</p>
                  </div>
                </div>

                <div class='message-grid'>
                  <article class='message-card'>
                    <h3>Instagram DM</h3>
                    <p>Shorter and more casual for social media outreach.</p>
                    <textarea id='instagram-message' class='outreach-copy' rows='9' readonly>{escape(generate_outreach_messages(prospect)['instagram_dm'])}</textarea>
                    <button class='btn-small copy-btn' type='button' data-copy-target='instagram-message'>Copy Instagram DM</button>
                  </article>

                  <article class='message-card'>
                    <h3>Email Version</h3>
                    <p>More polished for cold email or contact forms.</p>
                    <textarea id='email-message' class='outreach-copy' rows='12' readonly>{escape(generate_outreach_messages(prospect)['email_message'])}</textarea>
                    <button class='btn-small copy-btn' type='button' data-copy-target='email-message'>Copy Email</button>
                  </article>

                  <article class='message-card'>
                    <h3>Follow-Up Message</h3>
                    <p>Use this 2–4 days after the first message.</p>
                    <textarea id='followup-message' class='outreach-copy' rows='7' readonly>{escape(generate_outreach_messages(prospect)['follow_up'])}</textarea>
                    <button class='btn-small copy-btn' type='button' data-copy-target='followup-message'>Copy Follow-Up</button>
                  </article>
                </div>

                <div class='quick-actions'>
                  {f"<a class='btn-small' href='mailto:{escape(prospect.get('email') or '')}?subject=Quick idea for {escape(prospect.get('business_name') or 'your business')}&body={escape(generate_outreach_messages(prospect)['email_message'])}'>Open Email</a>" if prospect.get('email') else ""}
                </div>
              </section>
              """ if is_edit else ""}

              {f"""
              <section class='panel danger-panel'>
                <h2>Delete Prospect</h2>
                <p>This permanently removes this prospect from your pipeline.</p>
                <form class='delete-form' method='post' action='/admin/prospects/{prospect['id']}/delete' onsubmit="return window.confirm('Delete this prospect permanently? This cannot be undone.');">
                  <button class='btn danger-btn' type='submit'>Delete Prospect</button>
                </form>
              </section>
              """ if is_edit else ""}
            """,
        )



    def _split_upwork_jobs(self, pasted_text):
        text = (pasted_text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
        if not text:
            return []

        lines = [line.strip() for line in text.split("\n")]

        def is_posted_line(line):
            value = (line or "").lower().strip()
            return (
                value.startswith("posted ")
                or value == "posted today"
                or value == "posted yesterday"
                or "posted just now" in value
            )

        posted_indexes = [
            index
            for index, line in enumerate(lines)
            if is_posted_line(line)
        ]

        # If there is only one Upwork "Posted..." marker, this is almost always one full job post.
        if len(posted_indexes) <= 1:
            return [text]

        # For multiple pasted search-result cards, split at the likely title right before each Posted line.
        start_indexes = []
        for posted_index in posted_indexes:
            title_index = None

            for candidate in range(posted_index - 1, max(-1, posted_index - 5), -1):
                candidate_line = lines[candidate].strip()

                if not candidate_line:
                    continue

                lower_candidate = candidate_line.lower()

                if (
                    len(candidate_line) < 5
                    or len(candidate_line) > 150
                    or candidate_line.startswith("$")
                    or lower_candidate in {"fixed-price", "hourly", "intermediate", "expert", "entry level"}
                    or lower_candidate.startswith("send a proposal")
                    or lower_candidate.startswith("available connects")
                    or lower_candidate.startswith("proposals:")
                    or lower_candidate.startswith("interviewing:")
                    or lower_candidate.startswith("skills and expertise")
                    or lower_candidate.startswith("activity on this job")
                    or lower_candidate.startswith("about the client")
                ):
                    continue

                title_index = candidate
                break

            if title_index is not None:
                start_indexes.append(title_index)

        # Remove duplicates while keeping order.
        cleaned_starts = []
        for index in start_indexes:
            if index not in cleaned_starts:
                cleaned_starts.append(index)

        if len(cleaned_starts) <= 1:
            return [text]

        jobs = []
        for position, start_index in enumerate(cleaned_starts):
            end_index = cleaned_starts[position + 1] if position + 1 < len(cleaned_starts) else len(lines)
            chunk = "\n".join(lines[start_index:end_index]).strip()
            if len(chunk) > 80:
                jobs.append(chunk)

        return jobs[:20] if jobs else [text]

    def _extract_money_values(self, text):
        values = []
        for match in re.findall(r"\$\s*([0-9][0-9,]*(?:\.\d{1,2})?)", text or ""):
            try:
                values.append(float(match.replace(",", "")))
            except ValueError:
                continue
        return values

    def _extract_first_number_after_label(self, text, label):
        pattern = rf"{re.escape(label)}\s*:?\s*([0-9]+)"
        match = re.search(pattern, text or "", flags=re.IGNORECASE)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                return None
        return None

    def _upwork_decision_label(self, score):
        if score >= 80:
            return "Apply"
        if score >= 60:
            return "Maybe"
        return "Skip"

    def _portfolio_matches_for_upwork(self, lower_text):
        matches = []

        if any(word in lower_text for word in ["landing page", "small business", "business website", "website design", "website redesign", "redesign"]):
            matches.extend(["House of Visuals", "Creative Impressions", "Cleaning Demo"])

        if any(word in lower_text for word in ["real estate", "photography", "professional service", "consultant", "coach"]):
            matches.extend(["Creative Impressions", "House of Visuals"])

        if any(word in lower_text for word in ["calculator", "quote", "pricing calculator", "estimate", "estimator"]):
            matches.append("Cleaning Demo Quote Calculator")

        if any(word in lower_text for word in ["dashboard", "crm", "admin", "portal", "database", "tracker"]):
            matches.append("Jukebox Dashboard")

        if any(word in lower_text for word in ["ecommerce", "e-commerce", "product", "shop", "store", "checkout"]):
            matches.append("HOV Market Demo")

        if any(word in lower_text for word in ["interactive", "map", "floor plan", "prototype", "custom tool"]):
            matches.extend(["Jukebox dashboard/custom tools", "House of Visuals admin work"])

        cleaned = []
        for item in matches:
            if item not in cleaned:
                cleaned.append(item)

        return cleaned or ["House of Visuals", "Creative Impressions", "Cleaning Demo"]

    def _analyze_single_upwork_job(self, job_text, job_number=1):
        raw = job_text or ""
        lower = raw.lower()
        lines = [line.strip() for line in raw.splitlines() if line.strip()]

        title = "Upwork Job"
        for line in lines[:8]:
            if len(line) > 4 and not any(skip in line.lower() for skip in ["posted", "send a proposal", "available connects", "proposals:", "interviewing:"]):
                title = line[:120]
                break

        score = 50
        positives = []
        red_flags = []

        service_keywords = [
            "website", "landing page", "web design", "redesign", "small business",
            "service business", "responsive", "home page", "contact form"
        ]
        feature_keywords = [
            "calculator", "quote", "pricing", "booking", "contact form", "dashboard",
            "crm", "admin", "interactive", "map", "floor plan", "prototype", "form"
        ]
        niche_keywords = [
            "cleaning", "contractor", "real estate", "beauty", "medical", "consultant",
            "coach", "event", "restaurant", "ecommerce", "e-commerce", "photography",
            "home service", "service business"
        ]
        platform_flags = [
            "advanced wix studio", "wix studio", "webflow cms", "hostaway", "ghost",
            "bubble", "shopify app", "wordpress plugin", "woocommerce plugin",
            "mobile app", "ios app", "android app", "saas mvp", "marketplace app",
            "marketplace", "complex api"
        ]
        non_fit_flags = [
            "seo only", "seo specialist", "google ads", "facebook ads", "social media manager",
            "cold calling", "sales role", "lead generation only", "telemarketing"
        ]

        if any(word in lower for word in service_keywords):
            score += 15
            positives.append("Matches website, landing page, redesign, or service-business work.")

        if any(word in lower for word in feature_keywords):
            score += 15
            positives.append("Includes a form, calculator, dashboard, booking flow, or interactive feature.")

        if any(word in lower for word in niche_keywords):
            score += 5
            positives.append("Niche matches House of Visuals portfolio or target industries.")

        if any(phrase in lower for phrase in ["posted today", "posted 1 hour", "posted 2 hours", "posted 3 hours", "posted 4 hours", "posted 5 hours", "posted minutes", "posted just now"]):
            score += 10
            positives.append("Fresh post within roughly 24 hours.")
        elif "posted yesterday" in lower or re.search(r"posted\s+\d+\s+day", lower):
            positives.append("Recently posted within the last few days.")

        connects_required = self._extract_first_number_after_label(raw, "Send a proposal for")
        if connects_required is None:
            connect_match = re.search(r"([0-9]+)\s+Connects", raw, flags=re.IGNORECASE)
            connects_required = int(connect_match.group(1)) if connect_match else None

        if connects_required is not None and connects_required >= 15:
            score -= 10
            red_flags.append(f"High Connect cost: {connects_required} Connects.")

        proposals_text = ""
        proposals_count = None
        prop_match = re.search(r"Proposals:\s*([^\n]+)", raw, flags=re.IGNORECASE)
        if prop_match:
            proposals_text = prop_match.group(1).strip()
            number_match = re.search(r"([0-9]+)", proposals_text)
            if number_match:
                proposals_count = int(number_match.group(1))

        if proposals_text:
            proposals_lower = proposals_text.lower()

            if "50+" in proposals_text or (proposals_count is not None and proposals_count >= 50):
                score -= 20
                red_flags.append("Very crowded job: 50+ proposals.")
            elif "less than 5" in proposals_lower or "fewer than 5" in proposals_lower:
                score += 8
                positives.append("Low competition: fewer than 5 proposals.")
            elif proposals_count is not None and proposals_count < 5:
                score += 8
                positives.append("Low competition: fewer than 5 proposals.")
            elif proposals_count is not None and proposals_count <= 10:
                score += 5
                positives.append("Manageable competition: 5–10 proposals.")

        interviews_count = self._extract_first_number_after_label(raw, "Interviewing")
        if interviews_count is not None:
            if interviews_count == 0:
                score += 8
                positives.append("No interviews yet.")
            elif interviews_count >= 10:
                score -= 15
                red_flags.append(f"Too many interviews already: {interviews_count}.")
            elif interviews_count <= 1:
                positives.append("Only 0–1 interviews so far.")

        if "payment method verified" in lower or "payment verified" in lower:
            score += 5
            positives.append("Client payment appears verified.")

        money_values = self._extract_money_values(raw)
        budget = ""
        if money_values:
            if len(money_values) >= 2:
                budget = f"${int(money_values[0]):,}–${int(money_values[1]):,}"
            else:
                budget = f"${int(money_values[0]):,}"

            if any(500 <= value <= 2000 for value in money_values):
                score += 5
                positives.append("Budget falls in the preferred $500–$2,000 range.")

        if any(phrase in lower for phrase in ["content ready", "assets ready", "copy ready", "i have the content", "figma ready", "design ready", "logo ready"]):
            score += 5
            positives.append("Client appears to have content/assets ready.")

        if any(phrase in lower for phrase in ["clear scope", "one-time", "fixed-price", "simple website", "landing page", "contact form"]):
            score += 5
            positives.append("Scope appears fairly clear and one-time.")

        if any(flag in lower for flag in platform_flags):
            score -= 15
            red_flags.append("Requires platform-specific or complex technical experience that may not fit HOV right now.")

        if any(flag in lower for flag in non_fit_flags):
            score -= 20
            red_flags.append("Job appears outside HOV services, such as SEO-only, ads-only, sales, or cold calling.")

        if "50+" in lower and "proposals" in lower:
            if "Very crowded job: 50+ proposals." not in red_flags:
                score -= 20
                red_flags.append("Very crowded job: 50+ proposals.")

        if "already hired" in lower or "hires:" in lower and "1" in lower:
            score -= 10
            red_flags.append("Client may have already hired or started with someone.")

        if any(phrase in lower for phrase in ["vague", "not sure what i need", "need someone asap", "do everything", "full ecommerce", "full e-commerce"]):
            score -= 10
            red_flags.append("Scope may be vague or larger than it sounds.")

        if any(phrase in lower for phrase in ["full ecommerce", "full e-commerce", "saas", "marketplace", "mobile app"]) and money_values and max(money_values) < 2000:
            score -= 20
            red_flags.append("Large build with a low budget.")

        if not any(word in lower for word in service_keywords + feature_keywords):
            score -= 20
            red_flags.append("Not clearly related to websites, design, forms, dashboards, calculators, or custom tools.")

        if any(phrase in lower for phrase in ["expert", "expert level"]) and any(flag in lower for flag in platform_flags):
            score -= 10
            red_flags.append("Expert-only platform requirement may be too specific.")

        score = max(0, min(100, score))
        decision = self._upwork_decision_label(score)
        portfolio = self._portfolio_matches_for_upwork(lower)

        if any(word in lower for word in ["calculator", "quote", "pricing", "dashboard", "crm", "admin"]):
            timeline = "1–2 weeks depending on fields, logic, and revisions."
        elif any(word in lower for word in ["ecommerce", "e-commerce", "store", "shop"]):
            timeline = "2–3 weeks for an ecommerce-lite/product-focused build."
        elif any(word in lower for word in ["landing page", "one page"]):
            timeline = "3–5 business days if content/assets are ready."
        elif any(word in lower for word in ["redesign", "website"]):
            timeline = "1–2 weeks depending on page count and content readiness."
        else:
            timeline = "5–10 business days after scope is confirmed."

        if money_values:
            max_budget = max(money_values)
            if score >= 80:
                suggested_bid = f"Bid around ${int(max(300, min(max_budget, max_budget * 0.9))):,}, depending on final scope."
            elif score >= 60:
                suggested_bid = f"Bid carefully around ${int(max(300, min(max_budget, max_budget * 0.75))):,}, or ask scope questions first."
            else:
                suggested_bid = "Do not spend Connects unless the client clarifies scope or budget."
        else:
            suggested_bid = "Ask for budget first; if aligned, suggest a starter range around $500–$1,500."

        if decision == "Apply":
            short_reason = "Strong match for House of Visuals based on scope, timing, competition, budget, or portfolio fit."
        elif decision == "Maybe":
            short_reason = "Potential fit, but ask clarifying questions before spending too many Connects."
        else:
            short_reason = "Likely not worth the Connects based on competition, scope, budget, platform requirements, or fit."

        if not positives:
            positives.append("Some details may be useful, but the post needs more review.")

        if not red_flags:
            red_flags.append("No major red flags found from the pasted text.")

        questions = [
            "Do you already have the logo, copy, images, and brand colors ready?",
            "How many pages or sections do you need included?",
            "Do you need this built as a custom HTML/CSS/JS site, or inside a specific platform?",
            "What is your ideal launch date?",
        ]

        if any(word in lower for word in ["calculator", "quote", "pricing", "estimate"]):
            questions.append("Do you already have the pricing rules/formulas for the calculator?")

        if any(word in lower for word in ["booking", "appointment"]):
            questions.append("Do you want a simple booking request form or integration with a scheduling platform?")

        proposal = f"""Hi! We’re House of Visuals, a husband-wife creative team that builds clean, professional websites, landing pages, forms, quote calculators, dashboards, and custom web tools for small businesses.

Your project stood out because it sounds aligned with the type of practical, conversion-focused web work we build: clear design, responsive layout, strong calls-to-action, and simple tools/forms that help the business operate better.

A few relevant examples we can share include: {", ".join(portfolio)}.

Before giving a final timeline, we’d want to confirm the page count, content/assets, and whether you need a specific platform or a custom build. Based on what you posted, we could likely help with this and keep the process simple.

A few quick questions:
- Do you already have copy, images, and branding ready?
- What is your ideal launch date?
- Are there any forms, booking steps, calculators, or admin features needed?

Thanks!"""

        return {
            "title": title,
            "budget": budget or "Not listed",
            "connects_required": connects_required if connects_required is not None else "Not listed",
            "proposals": proposals_text or "Not listed",
            "interviews": interviews_count if interviews_count is not None else "Not listed",
            "score": score,
            "decision": decision,
            "short_reason": short_reason,
            "positive_signs": positives,
            "red_flags": red_flags,
            "suggested_bid": suggested_bid,
            "suggested_timeline": timeline,
            "suggested_portfolio": portfolio,
            "proposal_draft": proposal,
            "client_questions": questions,
            "pasted_text": raw,
        }

    def _analyze_upwork_jobs(self, pasted_text):
        chunks = self._split_upwork_jobs(pasted_text)
        return [
            self._analyze_single_upwork_job(chunk, index + 1)
            for index, chunk in enumerate(chunks)
        ]

    def _render_upwork_saved_jobs_table(self):
        query_params = parse_qs(self.path.split("?", 1)[1] if "?" in self.path else "")
        selected_status = query_params.get("status", [""])[0].strip()
        selected_decision = query_params.get("decision", [""])[0].strip()
        selected_sort = query_params.get("sort", ["created_at"])[0].strip() or "created_at"

        saved_jobs = get_upwork_scout_jobs(
            status_filter=selected_status,
            decision_filter=selected_decision,
            sort_by=selected_sort,
        )

        status_options = "<option value=''>All Statuses</option>" + "".join(
            f"<option value='{escape(status)}' {'selected' if selected_status == status else ''}>{escape(status)}</option>"
            for status in DEFAULT_UPWORK_SCOUT_STATUSES
        )

        decision_options = "<option value=''>All Decisions</option>" + "".join(
            f"<option value='{escape(decision)}' {'selected' if selected_decision == decision else ''}>{escape(decision)}</option>"
            for decision in ["Apply", "Maybe", "Skip"]
        )

        sort_options = "".join(
            f"<option value='{escape(value)}' {'selected' if selected_sort == value else ''}>{escape(label)}</option>"
            for value, label in [
                ("created_at", "Newest First"),
                ("score", "Highest Score"),
                ("connects", "Lowest Connects"),
                ("status", "Status"),
            ]
        )

        rows = []
        for job in saved_jobs:
            job_link = (
                f"<a class='btn-small' href='{escape(job.get('job_url') or '', quote=True)}' target='_blank' rel='noopener'>Open Job</a>"
                if job.get("job_url") else
                "<span class='mobile-muted'>No link saved</span>"
            )

            notes_preview = escape((job.get("notes") or "")[:140])
            if job.get("notes") and len(job.get("notes") or "") > 140:
                notes_preview += "..."

            rows.append(
                f"""
                <tr>
                  <td>
                    <strong>{escape(job.get('title') or 'Upwork Job')}</strong>
                    <span class="mobile-muted">Saved {escape(job.get('created_at') or '')}</span>
                    <div class="quick-actions">{job_link}</div>
                  </td>
                  <td><span class="score-pill">{escape(str(job.get('score') or 0))}/100</span></td>
                  <td><span class="priority-pill priority-{escape((job.get('decision_label') or 'Maybe').lower())}">{escape(job.get('decision_label') or 'Maybe')}</span></td>
                  <td>{escape(job.get('status') or 'New')}</td>
                  <td>
                    Required: {escape(str(job.get('connects_required') or '-'))}<br>
                    Spent: {escape(str(job.get('connects_spent') or '-'))}
                  </td>
                  <td>{notes_preview or '-'}</td>
                </tr>
                """
            )

        empty_state = """
            <tr>
              <td colspan="6">
                <div class="empty-state">
                  <h3>No saved Upwork jobs yet.</h3>
                  <p>Analyze a job above, then use Save Job to add it to this tracker.</p>
                </div>
              </td>
            </tr>
        """

        return f"""
            <section class="panel">
              <div class="panel-head">
                <div>
                  <h2>Saved Job Tracker</h2>
                  <p>Track jobs, statuses, Connects, notes, interviews, and wins.</p>
                </div>
                <a class="btn-small" href="/admin/upwork-scout">Reset Filters</a>
              </div>

              <form class="filters" method="get" action="/admin/upwork-scout">
                <label>Status
                  <select name="status">{status_options}</select>
                </label>

                <label>Decision
                  <select name="decision">{decision_options}</select>
                </label>

                <label>Sort
                  <select name="sort">{sort_options}</select>
                </label>

                <button class="btn" type="submit">Apply Filters</button>
              </form>

              <div class="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Job</th>
                      <th>Score</th>
                      <th>Decision</th>
                      <th>Status</th>
                      <th>Connects</th>
                      <th>Notes</th>
                    </tr>
                  </thead>
                  <tbody>{''.join(rows) if rows else empty_state}</tbody>
                </table>
              </div>
            </section>
        """

    def _render_upwork_scout(self, results=None, pasted_text=""):
        results = results or []
        pasted_text = pasted_text or ""

        if results:
            cards = []
            for index, job in enumerate(results, 1):
                positives = "".join(f"<li>{escape(item)}</li>" for item in job["positive_signs"])
                red_flags = "".join(f"<li>{escape(item)}</li>" for item in job["red_flags"])
                portfolio = "".join(f"<li>{escape(item)}</li>" for item in job["suggested_portfolio"])
                questions = "".join(f"<li>{escape(item)}</li>" for item in job["client_questions"])

                cards.append(f"""
                <article class="message-card">
                  <h3>{escape(job["title"])}</h3>
                  <p><span class="score-pill">Score: {job["score"]}/100</span> <span class="priority-pill priority-{escape(job["decision"].lower())}">{escape(job["decision"])}</span></p>
                  <dl class="details">
                    <dt>Budget</dt><dd>{escape(str(job["budget"]))}</dd>
                    <dt>Connects</dt><dd>{escape(str(job["connects_required"]))}</dd>
                    <dt>Proposals</dt><dd>{escape(str(job["proposals"]))}</dd>
                    <dt>Interviews</dt><dd>{escape(str(job["interviews"]))}</dd>
                    <dt>Suggested Bid</dt><dd>{escape(job["suggested_bid"])}</dd>
                    <dt>Timeline</dt><dd>{escape(job["suggested_timeline"])}</dd>
                  </dl>

                  <h3>Reason</h3>
                  <p>{escape(job["short_reason"])}</p>

                  <h3>Positive Signs</h3>
                  <ul>{positives}</ul>

                  <h3>Red Flags</h3>
                  <ul>{red_flags}</ul>

                  <h3>Best Portfolio Pieces</h3>
                  <ul>{portfolio}</ul>

                  <h3>Questions to Ask</h3>
                  <ul>{questions}</ul>

                  <h3>Draft Proposal</h3>
                  <textarea class="outreach-copy" rows="12" readonly>{escape(job["proposal_draft"])}</textarea>

                  <div class="quick-actions">
                    <button class="btn-small copy-btn" type="button" data-copy-target="proposal-{index}">Copy Proposal</button>
                  </div>

                  <form method="post" action="/admin/upwork-scout/save" class="score-checklist">
                    <h3>Save to Tracker</h3>
                    <input type="hidden" name="pasted_text" value="{escape(job["pasted_text"], quote=True)}" />

                    <label>Job Link
                      <input type="url" name="job_url" placeholder="Paste Upwork job link manually, optional" />
                    </label>

                    <label>Status
                      <select name="status">
                        <option value="New">New</option>
                        <option value="Applied">Applied</option>
                        <option value="Maybe">Maybe</option>
                        <option value="Skipped">Skipped</option>
                        <option value="Interview">Interview</option>
                        <option value="Hired">Hired</option>
                        <option value="Lost">Lost</option>
                      </select>
                    </label>

                    <label>Connects Spent
                      <input type="text" name="connects_spent" value="{escape(str(job["connects_required"]), quote=True) if str(job["connects_required"]) != "Not listed" else ""}" placeholder="Example: 8" />
                    </label>

                    <label>Notes
                      <textarea name="notes" rows="4" placeholder="Why you saved it, proposal angle, follow-up notes..."></textarea>
                    </label>

                    <button class="btn" type="submit">Save Job</button>
                  </form>

                  <textarea id="proposal-{index}" style="position:absolute;left:-9999px;">{escape(job["proposal_draft"])}</textarea>
                </article>
                """)

            results_html = f"""
            <section class="panel">
              <div class="panel-head">
                <div>
                  <h2>Analysis Results</h2>
                  <p>Showing {len(results)} analyzed job(s). This is based only on the text you manually pasted.</p>
                </div>
              </div>
              <div class="message-grid upwork-results-grid">{''.join(cards)}</div>
            </section>
            """
        else:
            results_html = """
            <section class="panel">
              <div class="panel-head">
                <div>
                  <h2>Analysis Results</h2>
                  <p>Analyzed jobs will appear here with scores, labels, red flags, portfolio suggestions, and proposal drafts.</p>
                </div>
              </div>

              <div class="empty-state">
                <h3>No jobs analyzed yet.</h3>
                <p>Paste Upwork text above and click Analyze Jobs.</p>
              </div>
            </section>
            """

        return self._admin_shell(
            "Upwork Scout",
            f"""
            <section class="hero">
              <p>Manual Upwork Decision Assistant</p>
              <h1>Upwork Scout</h1>
              <p>Paste job posts or copied search-result text here. This tool does not log into Upwork, scrape pages, auto-refresh, auto-click, or auto-apply.</p>
            </section>

            <section class="panel">
              <div class="panel-head">
                <div>
                  <h2>Analyze Upwork Jobs</h2>
                  <p>Use this to quickly decide if a job is worth your Connects.</p>
                </div>
              </div>

              <form method="post" action="/admin/upwork-scout/analyze">
                <label>Paste Upwork job post or search results here
                  <textarea name="upwork_text" rows="14" placeholder="Paste one full job post or multiple copied job cards from Upwork...">{escape(pasted_text)}</textarea>
                </label>

                <div class="quick-actions">
                  <button class="btn" type="submit">Analyze Jobs</button>
                  <a class="btn-small" href="/admin/upwork-scout">Clear</a>
                </div>
              </form>
            </section>

            {results_html}

            {self._render_upwork_saved_jobs_table()}
            """,
        )

    def _render_admin_overview(self):
        leads = get_leads()
        prospects = get_prospects()
        active_leads = [lead for lead in leads if lead.get("status") != "Completed"]
        completed_leads = [lead for lead in leads if lead.get("status") == "Completed"]

        today = datetime.now().strftime("%Y-%m-%d")
        new_leads = sum(1 for lead in active_leads if lead.get("status") == "New")
        contacted_leads = sum(1 for lead in active_leads if lead.get("status") == "Contacted")
        follow_up_due = sum(
            1 for prospect in prospects
            if prospect.get("next_follow_up") and prospect.get("next_follow_up") <= today
        )
        high_priority = sum(
            1 for prospect in prospects
            if (prospect.get("review_priority") or "").lower() == "high priority"
        )
        ready_to_contact = sum(
            1 for prospect in prospects
            if prospect.get("status") == "Ready to Contact"
        )

        summary_cards = f"""
            <article><strong>{len(active_leads)}</strong><span>Active Leads</span></article>
            <article><strong>{new_leads}</strong><span>New Leads</span></article>
            <article><strong>{len(prospects)}</strong><span>Total Prospects</span></article>
            <article><strong>{follow_up_due}</strong><span>Follow-Ups Due</span></article>
            <article><strong>{high_priority}</strong><span>High Priority</span></article>
            <article><strong>{len(completed_leads)}</strong><span>Completed Projects</span></article>
        """

        return self._admin_shell(
            "Admin Overview",
            f"""
            <section class="hero">
              <p>House of Visuals Command Center</p>
              <h1>Admin Overview</h1>
              <div class="quick-actions">
                <a class="btn" href="/admin/leads">View Leads</a>
                <a class="btn-small" href="/admin/prospects">View Prospects</a>
                <a class="btn-small" href="/admin/research">Research Helper</a>
                <a class="btn-small" href="/admin/upwork-scout">Upwork Scout</a>
              </div>
            </section>

            <section class="stats">{summary_cards}</section>

            <section class="panel">
              <div class="panel-head">
                <div>
                  <h2>Quick Actions</h2>
                  <p>Jump into the most common admin tasks without hunting through the dashboard.</p>
                </div>
              </div>

              <div class="admin-shortcuts">
                <a class="admin-shortcut" href="/admin/leads">
                  <strong>Leads</strong>
                  <span>Review website inquiries, update statuses, and follow up with potential clients.</span>
                </a>

                <a class="admin-shortcut" href="/admin/prospects">
                  <strong>Prospects</strong>
                  <span>Track businesses you may want to contact and prioritize outreach opportunities.</span>
                </a>

                <a class="admin-shortcut" href="/admin/prospects/new">
                  <strong>Add Prospect</strong>
                  <span>Add a business manually to your prospect pipeline.</span>
                </a>

                <a class="admin-shortcut" href="/admin/research">
                  <strong>Research Helper</strong>
                  <span>Find possible clients and identify businesses that may need website or branding help.</span>
                </a>

                <a class="admin-shortcut" href="/admin/prospects/import">
                  <strong>Import Prospects</strong>
                  <span>Paste CSV data and add multiple prospects into the pipeline faster.</span>
                </a>

                <a class="admin-shortcut" href="/admin/upwork-scout">
                  <strong>Upwork Scout</strong>
                  <span>Paste Upwork job text, analyze fit, and decide whether to apply before spending Connects.</span>
                </a>

                <a class="admin-shortcut" href="/admin/client-previews">
                  <strong>Client Previews</strong>
                  <span>Manage private demo links and client preview pages.</span>
                </a>

                <a class="admin-shortcut" href="/admin/completed">
                  <strong>Completed Projects</strong>
                  <span>View leads that have been moved into the completed project log.</span>
                </a>

                <a class="admin-shortcut" href="/admin/prospects?status=Ready%20to%20Contact">
                  <strong>Ready to Contact</strong>
                  <span>See prospects that are ready for outreach.</span>
                </a>
              </div>
            </section>

            <section class="panel">
              <div class="panel-head">
                <div>
                  <h2>Today’s Focus</h2>
                  <p>Use this snapshot to decide what needs attention first.</p>
                </div>
              </div>

              <div class="message-grid">
                <article class="message-card">
                  <h3>Follow-Ups Due</h3>
                  <p>{follow_up_due} prospect follow-up(s) are due today or overdue.</p>
                  <a class="btn-small" href="/admin/prospects">View Prospects</a>
                </article>

                <article class="message-card">
                  <h3>High Priority Prospects</h3>
                  <p>{high_priority} prospect(s) are marked high priority for review.</p>
                  <a class="btn-small" href="/admin/prospects">Review Pipeline</a>
                </article>

                <article class="message-card">
                  <h3>Ready to Contact</h3>
                  <p>{ready_to_contact} prospect(s) are ready for outreach.</p>
                  <a class="btn-small" href="/admin/prospects?status=Ready%20to%20Contact">Open List</a>
                </article>
              </div>
            </section>
            """
        )


    def _render_leads_dashboard(self):
        all_leads = get_leads()
        leads = [lead for lead in all_leads if lead.get("status") != "Completed"]

        query_params = parse_qs(self.path.split("?", 1)[1] if "?" in self.path else "")
        selected_status = query_params.get("status", [""])[0].strip()
        selected_service = query_params.get("service", [""])[0].strip()
        search_term = query_params.get("q", [""])[0].strip().lower()

        def lead_service_text(lead):
            services = lead.get("project_types") or []
            return ", ".join(services)

        filtered_leads = []
        for lead in leads:
            service_text = lead_service_text(lead)
            searchable_text = " ".join(
                [
                    str(lead.get("full_name") or ""),
                    str(lead.get("business_name") or ""),
                    str(lead.get("email") or ""),
                    str(lead.get("phone") or ""),
                    str(lead.get("timeline") or ""),
                    str(lead.get("budget") or ""),
                    service_text,
                ]
            ).lower()

            if selected_status and lead.get("status") != selected_status:
                continue

            if selected_service and selected_service.lower() not in service_text.lower():
                continue

            if search_term and search_term not in searchable_text:
                continue

            filtered_leads.append(lead)

        status_counts = {status: 0 for status in DEFAULT_LEAD_STATUSES}
        for lead in leads:
            status_counts[lead["status"]] = status_counts.get(lead["status"], 0) + 1

        all_services = sorted(
            {
                service
                for lead in leads
                for service in (lead.get("project_types") or [])
                if service
            }
        )

        total_leads = len(leads)
        new_leads = status_counts.get("New", 0)
        contacted_leads = status_counts.get("Contacted", 0)
        won_leads = status_counts.get("Won", 0)

        summary_cards = f"""
            <article><strong>{total_leads}</strong><span>Total Leads</span></article>
            <article><strong>{new_leads}</strong><span>New Leads</span></article>
            <article><strong>{contacted_leads}</strong><span>Contacted</span></article>
            <article><strong>{won_leads}</strong><span>Won Leads</span></article>
        """

        status_filter_options = "<option value=''>All Statuses</option>" + "".join(
            f"<option value='{escape(status)}' {'selected' if selected_status == status else ''}>{escape(status)}</option>"
            for status in DEFAULT_LEAD_STATUSES
        )

        service_filter_options = "<option value=''>All Services</option>" + "".join(
            f"<option value='{escape(service)}' {'selected' if selected_service == service else ''}>{escape(service)}</option>"
            for service in all_services
        )

        rows = []
        for lead in filtered_leads:
            service_text = lead_service_text(lead) or "-"
            rows.append(
                f"""
                <tr>
                  <td><a href="/admin/leads/{lead['id']}">#{lead['id']}</a></td>
                  <td>{escape(lead.get('submitted_at') or '')}</td>
                  <td>
                    <strong>{escape(lead.get('full_name') or 'Website Lead')}</strong>
                    <span class="mobile-muted">{escape(lead.get('email') or '')}</span>
                  </td>
                  <td>{escape(lead.get('business_name') or '-')}</td>
                  <td>{escape(lead.get('email') or '-')}</td>
                  <td>{escape(lead.get('phone') or '-')}</td>
                  <td>{escape(service_text)}</td>
                  <td>{escape(lead.get('budget') or '-')}</td>
                  <td><span class="status status-{escape((lead.get('status') or 'New').lower().replace(' ', '-'))}">{escape(lead.get('status') or 'New')}</span></td>
                  <td><a class="btn-small" href="/admin/leads/{lead['id']}">View Details</a></td>
                </tr>
                """
            )

        empty_state = """
            <tr>
              <td colspan="10">
                <div class="empty-state">
                  <h3>No leads match your filters.</h3>
                  <p>Try clearing your search, choosing another status, or submitting a new test inquiry.</p>
                  <a class="btn-small" href="/admin/leads">Clear Filters</a>
                </div>
              </td>
            </tr>
        """

        return self._admin_shell(
            "Leads Dashboard",
            f"""
            <section class="hero">
              <p>House of Visuals Lead Generator</p>
              <h1>Leads Dashboard</h1>
              <div class="quick-actions">
                <a class="btn" href="/contact.html">Add Lead</a>
                <a class="btn-small" href="/admin/leads/export">Export Leads CSV</a>
              </div>
            </section>

            <section class="stats stats-four">{summary_cards}</section>
<section class="panel">
              <div class="panel-head">
                <div>
                  <h2>Lead Filters</h2>
                  <p>Search, filter, and track your website inquiries.</p>
                </div>
                <a class="btn-small" href="/admin/leads">Reset</a>
              </div>

              <form class="filters" method="get" action="/admin/leads">
                <label>Search
                  <input type="search" name="q" value="{escape(query_params.get('q', [''])[0])}" placeholder="Name, email, phone, or business" />
                </label>

                <label>Status
                  <select name="status">{status_filter_options}</select>
                </label>

                <label>Service
                  <select name="service">{service_filter_options}</select>
                </label>

                <button class="btn" type="submit">Apply Filters</button>
              </form>
            </section>

            <section class="panel">
              <div class="panel-head">
                <div>
                  <h2>All Leads</h2>
                  <p>Showing {len(filtered_leads)} of {len(leads)} total submissions</p>
                </div>
              </div>

              <div class="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Date Submitted</th>
                      <th>Name</th>
                      <th>Business</th>
                      <th>Email</th>
                      <th>Phone</th>
                      <th>Service</th>
                      <th>Budget</th>
                      <th>Status</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>{''.join(rows) if rows else empty_state}</tbody>
                </table>
              </div>
            </section>
            """,
        )

    def _render_lead_detail(self, lead_id):
        lead = get_lead(lead_id)
        if not lead:
            self._send_html(self._admin_shell("Lead Not Found", "<section class='panel'><h1>Lead not found.</h1><a href='/admin/leads'>Back to leads</a></section>"), status=404)
            return

        status_options = "".join(
            f"<option value='{escape(status)}' {'selected' if status == lead['status'] else ''}>{escape(status)}</option>"
            for status in DEFAULT_LEAD_STATUSES
        )
        fields = lead.get("fields", {})
        field_rows = "".join(
            f"<dt>{escape(str(key))}</dt><dd>{escape(', '.join(value) if isinstance(value, list) else str(value or '-'))}</dd>"
            for key, value in fields.items()
        )

        html = self._admin_shell(
            f"Lead #{lead['id']}",
            f"""
            <section class="hero detail-hero">
              <p><a href="/admin/leads">← Back to Leads</a></p>
              <h1>Lead #{lead['id']}: {escape(lead.get('full_name') or 'Website Lead')}</h1>
              <p>Submitted {escape(lead.get('submitted_at') or '')}</p>
            </section>
            <section class="detail-grid">
              <article class="panel">
                <h2>Lead Details</h2>
                <dl class="details">
                  <dt>Full Name</dt><dd>{escape(lead.get('full_name') or '-')}</dd>
                  <dt>Business Name</dt><dd>{escape(lead.get('business_name') or '-')}</dd>
                  <dt>Email</dt><dd>{escape(lead.get('email') or '-')}</dd>
                  <dt>Phone</dt><dd>{escape(lead.get('phone') or '-')}</dd>
                  <dt>Website / Social</dt><dd>{escape(lead.get('website_social') or '-')}</dd>
                  <dt>Project Types</dt><dd>{escape(', '.join(lead.get('project_types') or []) or '-')}</dd>
                  <dt>Project Goals</dt><dd>{escape(', '.join(lead.get('project_goals') or []) or '-')}</dd>
                  <dt>Timeline</dt><dd>{escape(lead.get('timeline') or '-')}</dd>
                  <dt>Budget</dt><dd>{escape(lead.get('budget') or '-')}</dd>
                  <dt>Referral Source</dt><dd>{escape(lead.get('referral_source') or '-')}</dd>
                  <dt>Email Status</dt><dd>{escape(lead.get('email_status') or '-')}</dd>
                </dl>
              </article>
              <article class="panel">
                <h2>Status + Internal Notes</h2>
                <form method="post" action="/admin/leads/{lead['id']}">
                  <label>Status
                    <select name="status">{status_options}</select>
                  </label>
                  <label>Internal Notes
                    <textarea name="internal_notes" rows="10">{escape(lead.get('internal_notes') or '')}</textarea>
                  </label>
                  <button class="btn" type="submit">Save Lead</button>
                </form>
              </article>
            </section>
            <section class="panel">
              <h2>Full Submission</h2>
              <dl class="details full-fields">{field_rows}</dl>
            </section>

            <section class="panel danger-panel">
              <h2>Delete Lead</h2>
              <p>This permanently removes this lead from your dashboard.</p>
              <form class="delete-form" method="post" action="/admin/leads/{lead['id']}/delete" onsubmit="return window.confirm('Delete this lead permanently? This cannot be undone.');">
                <button class="btn danger-btn" type="submit">Delete Lead</button>
              </form>
            </section>
            """,
        )
        self._send_html(html)

    def _render_client_preview_landing_page(self, filename, client_slug):
        page_path = PROJECT_DIR / filename

        if not page_path.exists():
            self._send_html("<h1>Client preview not found.</h1>", status=404)
            return

        html = page_path.read_text(encoding="utf-8")
        loom_link = ""

        for preview in get_client_previews(include_inactive=False):
            demo_link = (preview.get("demo_link") or "").lower()
            business_name = (preview.get("business_name") or "").lower()

            slug_match = f"/client-preview/{client_slug}" in demo_link
            name_match = client_slug.replace("-", " ") in business_name

            if slug_match or name_match:
                loom_link = (preview.get("loom_link") or "").strip()
                break

        loom_button = ""

        if loom_link:
            loom_button = (
                f'<a class="preview-btn secondary" '
                f'href="{escape(loom_link, quote=True)}" '
                f'target="_blank" rel="noopener noreferrer">'
                f'Watch Loom Walkthrough</a>'
            )

        loom_placeholder = "<!-- CLIENT_LOOM_BUTTON -->"

        if loom_placeholder in html:
            html = html.replace(loom_placeholder, loom_button)
        elif loom_button:
            actions_marker = '<div class="preview-actions">'
            actions_start = html.find(actions_marker)

            if actions_start != -1:
                actions_end = html.find("</div>", actions_start)

                if actions_end != -1:
                    html = (
                        html[:actions_end]
                        + f"        {loom_button}\n      "
                        + html[actions_end:]
                    )

        self._send_html(html)


    def _render_client_previews(self):
        sync_client_preview_folders()
        previews = get_client_previews(include_inactive=True)
        cards = []

        for preview in previews:
            preview_id = preview.get("id")
            business_name = escape(preview.get("business_name") or "Unnamed Business")
            demo_link = (preview.get("demo_link") or "").strip()
            loom_link = (preview.get("loom_link") or "").strip()
            notes = escape(preview.get("notes") or "")
            is_active = int(preview.get("is_active") or 0) == 1
            status_label = "Active" if is_active else "Inactive"

            demo_button = (
                f'<a class="btn-small" href="{escape(demo_link, quote=True)}" target="_blank" rel="noopener">View Client Preview</a>'
                if demo_link else
                '<span class="preview-disabled">No Preview Link</span>'
            )

            loom_button = (
                f'<a class="btn-small" href="{escape(loom_link, quote=True)}" target="_blank" rel="noopener">Open Loom</a>'
                if loom_link else
                '<span class="preview-disabled">No Loom Link</span>'
            )

            delete_button = f"""
            <form action="/admin/client-previews/delete" method="POST" class="inline-form" onsubmit="return confirm('Delete this client preview permanently? This cannot be undone.');">
              <input type="hidden" name="preview_id" value="{preview_id}">
              <button class="btn-small danger-btn" type="submit">Delete</button>
            </form>
            """

            cards.append(
                f"""
                <article class="preview-card {'inactive-card' if not is_active else ''}">
                  <div class="preview-card-head">
                    <div>
                      <p class="preview-type">Client Preview</p>
                      <h2>{business_name}</h2>
                    </div>
                    <span class="status">{status_label}</span>
                  </div>

                  <div class="preview-actions">
                    {demo_button}
                    {loom_button}
                    <a class="btn-small" href="/admin/client-previews/{preview_id}/edit">Edit</a>
                    {delete_button}
                  </div>

                  <div class="preview-notes">
                    <strong>Notes</strong>
                    <p>{notes or 'No notes added.'}</p>
                  </div>
                </article>
                """
            )

        if not cards:
            cards.append(
                """
                <article class="preview-card">
                  <div class="preview-card-head">
                    <div>
                      <p class="preview-type">Client Preview</p>
                      <h2>No client previews added yet</h2>
                    </div>
                  </div>
                  <p class="preview-empty">Click “Add Client Preview” to save your first demo link.</p>
                </article>
                """
            )

        html = self._admin_shell(
            "Client Preview Directory",
            f"""
            <style>
              .preview-grid {{
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 1rem;
              }}

              .preview-card {{
                border: 1px solid var(--line);
                border-radius: 18px;
                background: rgba(255, 255, 255, 0.96);
                box-shadow: 0 14px 24px rgba(13, 32, 23, 0.08);
                padding: 1rem;
              }}

              .inactive-card {{
                opacity: 0.68;
              }}

              .preview-card-head {{
                display: flex;
                justify-content: space-between;
                gap: 1rem;
                align-items: flex-start;
                margin-bottom: 1rem;
              }}

              .preview-card h2 {{
                margin: 0;
                font-family: Georgia, serif;
                font-size: 1.55rem;
                color: var(--green);
              }}

              .preview-type {{
                margin: 0 0 0.25rem;
                color: var(--muted);
                font-weight: 900;
                font-size: 0.82rem;
                text-transform: uppercase;
                letter-spacing: 0.05em;
              }}

              .preview-actions {{
                display: flex;
                flex-wrap: wrap;
                gap: 0.55rem;
                align-items: center;
                margin-bottom: 1rem;
              }}

              .inline-form {{
                margin: 0;
              }}

              .preview-disabled {{
                display: inline-flex;
                align-items: center;
                min-height: 34px;
                border-radius: 999px;
                padding: 0.45rem 0.75rem;
                background: #eef1f4;
                color: #60707a;
                font-size: 0.86rem;
                font-weight: 900;
              }}

              .preview-notes {{
                border-top: 1px solid rgba(15, 74, 51, 0.12);
                padding-top: 0.85rem;
              }}

              .preview-notes strong {{
                display: block;
                color: var(--green);
                margin-bottom: 0.25rem;
              }}

              .preview-notes p,
              .preview-empty {{
                margin: 0;
                color: var(--muted);
                line-height: 1.55;
              }}

              @media (max-width: 850px) {{
                .preview-grid {{
                  grid-template-columns: 1fr;
                }}

                .preview-card-head {{
                  display: block;
                }}

                .preview-card-head .status {{
                  margin-top: 0.65rem;
                }}

                .preview-actions .btn-small,
                .preview-actions .preview-disabled,
                .inline-form,
                .inline-form button {{
                  width: 100%;
                }}
              }}
            </style>

            <section class="hero">
              <p>House of Visuals Admin</p>
              <h1>Client Preview Directory</h1>
            </section>

            <section class="panel">
              <div class="panel-head">
                <div>
                  <h2>Client Preview Directory</h2>
                  <p>Manage each client’s preview page, Loom walkthrough, internal notes, and review link in one place.</p>
                </div>
              </div>

              <div class="preview-grid">
                {''.join(cards)}
              </div>
            </section>
            """,
        )
        self._send_html(html)

    def _render_client_preview_form(self):
        html = self._admin_shell(
            "Add Client Preview",
            """
            <section class="hero">
              <p>House of Visuals Admin</p>
              <h1>Add Client Preview</h1>
              <a class="btn" href="/admin/client-previews">Back to Client Directory</a>
            </section>

            <section class="panel">
              <div class="panel-head">
                <div>
                  <h2>New Client Preview</h2>
                  <p>Add the client name, client-facing preview page, optional Loom walkthrough, and internal notes.</p>
                </div>
              </div>

              <form method="POST" action="/admin/client-previews/new">
                <label>
                  Business Name
                  <input type="text" name="business_name" placeholder="House of Visuals Co." required>
                </label>

                <label>
                  Client Preview Link
                  <input type="text" name="demo_link" placeholder="/client-preview/client-name/" required>
                </label>

                <label>
                  Loom Link
                  <input type="url" name="loom_link" placeholder="https://www.loom.com/share/...">
                </label>

                <label>
                  Notes
                  <textarea name="notes" placeholder="Example: Sent preview link and Loom walkthrough on June 2. Waiting for client feedback."></textarea>
                </label>

                <button class="btn" type="submit">Save Client Preview</button>
              </form>
            </section>
            """,
        )
        self._send_html(html)

    def _render_client_preview_edit_form(self, preview_id):
        preview = get_client_preview(preview_id)

        if not preview:
            self._send_html(
                self._admin_shell(
                    "Client Preview Not Found",
                    """
                    <section class="panel">
                      <h1>Client preview not found.</h1>
                      <a class="btn" href="/admin/client-previews">Back to Client Directory</a>
                    </section>
                    """,
                ),
                status=404,
            )
            return

        business_name = escape(preview.get("business_name") or "", quote=True)
        demo_link = escape(preview.get("demo_link") or "", quote=True)
        loom_link = escape(preview.get("loom_link") or "", quote=True)
        notes = escape(preview.get("notes") or "")

        html = self._admin_shell(
            "Edit Client Preview",
            f"""
            <section class="hero">
              <p>House of Visuals Admin</p>
              <h1>Edit Client Preview</h1>
              <a class="btn" href="/admin/client-previews">Back to Client Directory</a>
            </section>

            <section class="panel">
              <div class="panel-head">
                <div>
                  <h2>{escape(preview.get("business_name") or "Client Preview")}</h2>
                  <p>Update the client preview link, Loom walkthrough, business name, or internal notes.</p>
                </div>
              </div>

              <form method="POST" action="/admin/client-previews/{preview_id}/edit">
                <label>
                  Business Name
                  <input type="text" name="business_name" value="{business_name}" required>
                </label>

                <label>
                  Client Preview Link
                  <input type="text" name="demo_link" value="{demo_link}" required>
                </label>

                <label>
                  Loom Link
                  <input type="url" name="loom_link" value="{loom_link}">
                </label>

                <label>
                  Notes
                  <textarea name="notes" rows="8">{notes}</textarea>
                </label>

                <button class="btn" type="submit">Save Changes</button>
              </form>
            </section>
            """,
        )

        self._send_html(html)

    def _admin_shell(self, title, body):
        current_path = self.path.split("?", 1)[0]

        def nav_class(*paths):
            return "active" if current_path in paths else ""

        return f"""
        <!doctype html>
        <html lang="en">
          <head>
            <meta charset="utf-8" />
            <meta name="viewport" content="width=device-width, initial-scale=1" />
            <meta name="robots" content="noindex, nofollow" />
            <title>{escape(title)} | House of Visuals Admin</title>
            <style>
              :root {{
                --bg: #080c09;
                --panel: #ffffff;
                --ink: #142119;
                --muted: #516257;
                --green: #0f4a33;
                --gold: #c9a24f;
                --cream: #f7f1e4;
                --line: rgba(15, 74, 51, 0.16);
              }}
              * {{ box-sizing: border-box; }}
              body {{
                margin: 0;
                font-family: Manrope, Inter, system-ui, sans-serif;
                color: var(--ink);
                background: linear-gradient(160deg, #f8f4eb, #eef7f0);
              }}
              a {{ color: inherit; }}
              .wrap {{ width: min(100% - 2rem, 1180px); margin: 0 auto; padding: 1.2rem 0 3rem; }}
              .hero {{
                border-radius: 18px;
                background: linear-gradient(145deg, #0b130f, #123b2b);
                color: var(--cream);
                padding: clamp(1rem, 3vw, 1.6rem);
                margin-bottom: 1rem;
                border: 1px solid rgba(201, 162, 79, 0.3);
              }}
              .hero p {{ color: #ead7a7; margin: 0 0 0.45rem; }}
              .hero h1 {{ margin: 0; font-family: Georgia, serif; font-size: clamp(2rem, 5vw, 3.3rem); line-height: 1.05; }}
              .btn, .btn-small {{
                display: inline-flex;
                align-items: center;
                justify-content: center;
                border: 0;
                border-radius: 999px;
                background: linear-gradient(135deg, #1f7a57, #29a16f);
                color: #fff;
                font-weight: 800;
                text-decoration: none;
                cursor: pointer;
              }}
              .btn,
              .btn-small,
              .admin-nav a,
              .quick-actions a,
              .quick-actions button {{
                display: inline-flex;
                align-items: center;
                justify-content: center;
                gap: 0.35rem;
                border: 0;
                border-radius: 999px;
                font-weight: 900;
                text-decoration: none;
                cursor: pointer;
                line-height: 1;
                white-space: nowrap;
                transition: transform 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease;
              }}

              .btn {{
                min-height: 44px;
                padding: 0.78rem 1.1rem;
                margin-top: 0;
                background: linear-gradient(135deg, #1f7a57, #29a16f);
                color: #fff;
                box-shadow: 0 10px 18px rgba(31, 122, 87, 0.18);
              }}

              .btn-small,
              .admin-nav a,
              .quick-actions a:not(.btn),
              .quick-actions button:not(.btn) {{
                min-height: 38px;
                padding: 0.58rem 0.85rem;
                font-size: 0.88rem;
                background: #fffdf7;
                color: var(--green);
                border: 1px solid rgba(15, 74, 51, 0.16);
                box-shadow: 0 8px 15px rgba(13, 32, 23, 0.06);
              }}

              .btn:hover,
              .btn-small:hover,
              .admin-nav a:hover,
              .quick-actions a:hover,
              .quick-actions button:hover {{
                transform: translateY(-1px);
              }}

              .quick-actions {{
                display: flex;
                align-items: center;
                gap: 0.55rem;
                flex-wrap: wrap;
              }}

              .admin-nav {{
                display: flex;
                align-items: center;
                gap: 0.5rem;
                flex-wrap: wrap;
              }}

              .admin-nav a.active {{
                background: linear-gradient(135deg, #0f4a33, #1f7a57);
                color: #fff;
                border-color: rgba(201, 162, 79, 0.45);
                box-shadow: 0 10px 18px rgba(15, 74, 51, 0.16);
              }}

              .admin-nav a[href="/admin/logout"] {{
                background: #fff1ed;
                color: #8a2d1f;
                border-color: rgba(138, 45, 31, 0.2);
              }}

              .panel-head .quick-actions,
              .hero .quick-actions {{
                margin-top: 0.75rem;
              }}
              .admin-nav {{
                display: flex;
                flex-wrap: wrap;
                gap: 0.6rem;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 1rem;
                padding: 0.75rem 0;
              }}
              .admin-nav strong {{
                color: var(--green);
                font-family: Georgia, serif;
                font-size: 1.15rem;
              }}
              .admin-nav div {{
                display: flex;
                flex-wrap: wrap;
                gap: 0.5rem;
              }}
              .admin-nav a {{
                border: 1px solid rgba(15, 74, 51, 0.18);
                border-radius: 999px;
                background: rgba(255, 255, 255, 0.75);
                color: var(--green);
                font-weight: 900;
                padding: 0.5rem 0.75rem;
                text-decoration: none;
              }}
              .score-pill {{
                display: inline-flex;
                padding: 0.28rem 0.55rem;
                border-radius: 999px;
                background: #fff7df;
                color: #7a5818;
                font-weight: 900;
              }}
              .priority-pill {{
                display: inline-flex;
                padding: 0.28rem 0.55rem;
                border-radius: 999px;
                font-weight: 900;
                background: #edf6f0;
                color: var(--green);
              }}
              .priority-high-priority {{
                background: #fff1ed;
                color: #8a2d1f;
              }}
              .priority-medium-priority {{
                background: #fff7df;
                color: #7a5818;
              }}
              .priority-low-priority {{
                background: #edf6f0;
                color: var(--green);
              }}
              .priority-manual-review {{
                background: #eef1f4;
                color: #41505a;
              }}
              tr.followup-due td {{
                background: #fff9e8;
              }}
              tr.followup-due td:first-child {{
                border-left: 4px solid var(--gold);
              }}
              .outreach-panel {{
                margin-top: 1rem;
              }}
              .outreach-copy {{
                min-height: 220px;
                line-height: 1.55;
                background: #fffdf7;
              }}
              .quick-actions {{
                display: flex;
                flex-wrap: wrap;
                gap: 0.65rem;
                margin-top: 0.85rem;
              }}
              .message-grid {{
                display: grid;
                grid-template-columns: repeat(3, minmax(0, 1fr));
                gap: 1rem;
              }}
              .message-card {{
                border: 1px solid rgba(15, 74, 51, 0.14);
                border-radius: 16px;
                background: rgba(255, 255, 255, 0.75);
                padding: 1rem;
              }}
              .message-card h3 {{
                margin: 0 0 0.35rem;
                font-family: Georgia, serif;
                font-size: 1.2rem;
                color: var(--green);
              }}
              .message-card p {{
                margin: 0 0 0.75rem;
                color: var(--muted);
              }}
              .upwork-results-grid {{
                grid-template-columns: 1fr;
              }}
              .upwork-results-grid .message-card {{
                width: 100%;
              }}
              .copy-btn {{
                margin-top: 0.75rem;
                width: 100%;
              }}
              .copy-btn.copied {{
                background: linear-gradient(135deg, #0f4a33, #1f7a57);
              }}
              .score-checklist {{
                border: 1px solid rgba(15, 74, 51, 0.14);
                border-radius: 16px;
                background: #fffdf7;
                padding: 1rem;
                margin-bottom: 0.85rem;
              }}
              .score-checklist h3 {{
                margin: 0 0 0.35rem;
                font-family: Georgia, serif;
                font-size: 1.2rem;
                color: var(--green);
              }}
              .score-checklist p {{
                margin: 0 0 0.85rem;
                color: var(--muted);
              }}
              .check-row {{
                display: grid;
                grid-template-columns: auto 1fr auto;
                align-items: center;
                gap: 0.65rem;
                margin: 0;
                padding: 0.6rem 0;
                border-top: 1px solid rgba(15, 74, 51, 0.1);
                color: var(--ink);
                font-weight: 800;
              }}
              .check-row input {{
                width: auto;
                transform: scale(1.1);
              }}
              .check-row strong {{
                color: var(--green);
              }}
              .danger-panel {{
                border-color: rgba(138, 45, 31, 0.22);
                background: #fff7f4;
              }}
              .danger-panel h2 {{
                color: #8a2d1f;
              }}
              .danger-btn {{
                background: linear-gradient(135deg, #8a2d1f, #c33d2b);
              }}
              .multi-dropdown {{
                width: 100%;
                border: 1px solid rgba(15, 74, 51, 0.22);
                border-radius: 12px;
                background: #fff;
                color: var(--ink);
                overflow: hidden;
              }}
              .multi-dropdown summary {{
                cursor: pointer;
                list-style: none;
                padding: 0.75rem;
                font-weight: 900;
                color: var(--green);
              }}
              .multi-dropdown summary::-webkit-details-marker {{
                display: none;
              }}
              .multi-dropdown summary::after {{
                content: "▼";
                float: right;
                font-size: 0.8rem;
              }}
              .multi-dropdown[open] summary::after {{
                content: "▲";
              }}
              .multi-dropdown-menu {{
                border-top: 1px solid rgba(15, 74, 51, 0.12);
                padding: 0.4rem 0.75rem 0.75rem;
                max-height: 280px;
                overflow-y: auto;
              }}
              .multi-dropdown .check-row {{
                grid-template-columns: auto 1fr;
              }}
              .multi-dropdown .check-row strong {{
                display: none;
              }}
              .stats {{ display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 0.75rem; margin-bottom: 1rem; }}
.stats-four {{ grid-template-columns: repeat(4, minmax(0, 1fr)); }}
              .stats article, .panel {{
                border: 1px solid var(--line);
                border-radius: 16px;
                background: rgba(255, 255, 255, 0.94);
                box-shadow: 0 14px 24px rgba(13, 32, 23, 0.08);
              }}
              .stats article {{ padding: 0.85rem; }}
              .stats strong {{ display: block; font-size: 1.7rem; color: var(--green); }}
              .stats span {{ color: var(--muted); font-weight: 800; font-size: 0.86rem; }}
              .panel {{ padding: 1rem; margin-bottom: 1rem; }}
              .panel-head {{ display: flex; justify-content: space-between; gap: 1rem; align-items: end; margin-bottom: 0.75rem; }}
              .panel h2 {{ margin: 0 0 0.75rem; font-family: Georgia, serif; font-size: 1.45rem; }}
              .panel p {{ color: var(--muted); margin: 0; }}
              .admin-shortcuts {{
                display: grid;
                grid-template-columns: repeat(4, minmax(0, 1fr));
                gap: 0.75rem;
              }}
              .admin-shortcut {{
                display: grid;
                gap: 0.35rem;
                border: 1px solid rgba(15, 74, 51, 0.14);
                border-radius: 16px;
                background: #fffdf7;
                padding: 0.9rem;
                text-decoration: none;
                box-shadow: 0 10px 18px rgba(13, 32, 23, 0.06);
              }}
              .admin-shortcut strong {{
                color: var(--green);
                font-size: 1rem;
              }}
              .admin-shortcut span {{
                color: var(--muted);
                font-size: 0.9rem;
                line-height: 1.4;
              }}
              .admin-shortcut:hover {{
                transform: translateY(-1px);
                border-color: rgba(201, 162, 79, 0.45);
              }}

              .table-wrap {{ overflow-x: auto; }}
              table {{ width: 100%; border-collapse: collapse; min-width: 760px; }}
              th, td {{ padding: 0.72rem; text-align: left; border-bottom: 1px solid rgba(15, 74, 51, 0.12); vertical-align: top; }}
              th {{ color: var(--green); font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.04em; }}
              .status {{ display: inline-flex; padding: 0.28rem 0.55rem; border-radius: 999px; background: #edf6f0; color: var(--green); font-weight: 800; }}
              .detail-grid {{ display: grid; grid-template-columns: 1.1fr 0.9fr; gap: 1rem; }}
              .details {{ display: grid; grid-template-columns: minmax(120px, 0.45fr) 1fr; gap: 0.55rem 0.8rem; margin: 0; }}
              .details dt {{ color: var(--muted); font-weight: 800; }}
              .details dd {{ margin: 0; overflow-wrap: anywhere; }}
              .full-fields {{ grid-template-columns: minmax(150px, 0.35fr) 1fr; }}
              label {{ display: grid; gap: 0.4rem; font-weight: 800; color: var(--green); margin-bottom: 0.85rem; }}
             select, textarea, input {{
                width: 100%;
                border: 1px solid rgba(15, 74, 51, 0.22);
                border-radius: 12px;
                padding: 0.7rem;
                font: inherit;
                color: var(--ink);
                background: #fff;
              }}
.filters {{
  display: grid;
  grid-template-columns: 1.4fr 1fr 1fr auto;
  gap: 0.75rem;
  align-items: end;
}}

.filters label {{
  margin-bottom: 0;
}}

.filters .btn {{
  margin-top: 0;
  min-width: 140px;
}}

.mobile-muted {{
  display: none;
  color: var(--muted);
  font-size: 0.82rem;
  margin-top: 0.15rem;
}}

.empty-state {{
  text-align: center;
  padding: 2rem 1rem;
}}

.empty-state h3 {{
  margin: 0 0 0.4rem;
  font-family: Georgia, serif;
  font-size: 1.4rem;
}}

.empty-state p {{
  margin-bottom: 1rem;
}}
              @media (max-width: 850px) {{
                .wrap {{ width: min(100% - 1rem, 1180px); }}
                .stats, .stats-four, .detail-grid, .filters, .message-grid, .admin-shortcuts {{ grid-template-columns: 1fr; }}
                .panel-head {{ display: block; }}
                .details, .full-fields {{ grid-template-columns: 1fr; }}
                .btn {{ width: 100%; }}
		.mobile-muted {{ display: block; }}
              }}
            </style>
          </head>
          <body>
            <main class="wrap">
              <nav class="admin-nav" aria-label="Admin navigation">
                <strong>House of Visuals Admin</strong>
                <div>
                  <a class="{nav_class('/admin', '/admin/')}" href="/admin">Overview</a>
                  <a class="{nav_class('/admin/leads', '/admin/leads/')}" href="/admin/leads">Leads</a>
                  <a class="{nav_class('/admin/prospects', '/admin/prospects/')}" href="/admin/prospects">Prospects</a>
                  <a class="{nav_class('/admin/prospects/new', '/admin/prospects/new/')}" href="/admin/prospects/new">Add Prospect</a>
                  <a class="{nav_class('/admin/prospects/import', '/admin/prospects/import/')}" href="/admin/prospects/import">Import</a>
                  <a class="{nav_class('/admin/research', '/admin/research/')}" href="/admin/research">Research</a>
                  <a class="{nav_class('/admin/upwork-scout', '/admin/upwork-scout/')}" href="/admin/upwork-scout">Upwork Scout</a>
                  <a class="{nav_class('/admin/client-previews', '/admin/client-previews/')}" href="/admin/client-previews">Client Previews</a>
                  <a class="{nav_class('/admin/completed', '/admin/completed/')}" href="/admin/completed">Completed</a>
                  <a href="/admin/logout">Logout</a>
                </div>
              </nav>
              {body}
            </main>
            <script>
              document.addEventListener("DOMContentLoaded", function () {{
                const checks = Array.from(document.querySelectorAll(".score-check"));
                const scoreInput = document.getElementById("lead_score");

                if (!checks.length || !scoreInput) return;

                function updateScore() {{
                  const total = checks.reduce(function (sum, checkbox) {{
                    return sum + (checkbox.checked ? Number(checkbox.dataset.score || 0) : 0);
                  }}, 0);

                  scoreInput.value = Math.min(10, total);
                }}

                checks.forEach(function (checkbox) {{
                  checkbox.addEventListener("change", updateScore);
                }});

                const copyButtons = Array.from(document.querySelectorAll(".copy-btn"));
                copyButtons.forEach(function (button) {{
                  button.addEventListener("click", async function () {{
                    const targetId = button.dataset.copyTarget;
                    const target = document.getElementById(targetId);
                    if (!target) return;

                    const text = target.value || target.textContent || "";

                    try {{
                      await navigator.clipboard.writeText(text);
                      const originalText = button.textContent;
                      button.textContent = "Copied!";
                      button.classList.add("copied");

                      setTimeout(function () {{
                        button.textContent = originalText;
                        button.classList.remove("copied");
                      }}, 1600);
                    }} catch (error) {{
                      target.focus();
                      target.select();
                      document.execCommand("copy");
                      const originalText = button.textContent;
                      button.textContent = "Copied!";
                      setTimeout(function () {{
                        button.textContent = originalText;
                      }}, 1600);
                    }}
                  }});
                }});
              }});
            </script>
          </body>
        </html>
        """

    def _save_inquiry_locally(self, fields, reason):
        INQUIRY_DIR.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        safe_name = fields.get("full_name", ["website-lead"])[0].strip().lower().replace(" ", "-") or "website-lead"
        output_path = INQUIRY_DIR / f"{timestamp}-{safe_name}.json"
        payload = {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "status": "saved_locally",
            "reason_email_not_sent": reason,
            "fields": fields,
        }
        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return output_path

    def _save_testimonial_locally(self, fields, reason):
        TESTIMONIAL_DIR.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        safe_name = fields.get("full_name", ["testimonial"])[0].strip().lower().replace(" ", "-") or "testimonial"
        output_path = TESTIMONIAL_DIR / f"{timestamp}-{safe_name}.json"
        payload = {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "status": "saved_locally",
            "reason_email_not_sent": reason,
            "fields": fields,
        }
        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return output_path

    def _send_inquiry_email(self, fields):
        smtp_host = os.getenv("HOV_SMTP_HOST")
        smtp_port = int(os.getenv("HOV_SMTP_PORT", "587"))
        smtp_user = os.getenv("HOV_SMTP_USER")
        smtp_pass = os.getenv("HOV_SMTP_PASS")
        smtp_from = os.getenv("HOV_SMTP_FROM", smtp_user or "")
        inquiry_to = os.getenv("HOV_INQUIRY_TO")
        use_ssl = os.getenv("HOV_SMTP_SSL", "false").lower() in {"1", "true", "yes"}

        missing = [
            name
            for name, value in [
                ("HOV_SMTP_HOST", smtp_host),
                ("HOV_SMTP_USER", smtp_user),
                ("HOV_SMTP_PASS", smtp_pass),
                ("HOV_SMTP_FROM", smtp_from),
                ("HOV_INQUIRY_TO", inquiry_to),
            ]
            if not value
        ]
        if missing:
            raise RuntimeError(f"Missing email env vars: {', '.join(missing)}")

        def first(name):
            values = fields.get(name, [])
            return values[0].strip() if values else ""

        def first_of(*names):
            for name in names:
                value = first(name)
                if value:
                    return value
            return ""

        def many(name):
            return [v.strip() for v in fields.get(name, []) if v.strip()]

        lines = [
            "New House of Visuals Inquiry",
            "",
            "Contact Info",
            f"Full Name: {first('full_name')}",
            f"Business Name: {first('business_name')}",
            f"Email: {first('email')}",
            f"Phone: {first('phone')}",
            f"Website/Social: {first_of('website_social_links', 'website_social')}",
            "",
            "Project Type (multi-select)",
            ", ".join(many("project_type[]")) or "-",
            "",
            "Business Details",
            f"About Business: {first('business_overview')}",
            f"Offer: {first('offerings')}",
            f"Target Audience: {first('target_audience')}",
            f"Unique Value: {first('unique_value')}",
            "",
            "Project Goals (multi-select)",
            ", ".join(many("project_goal[]")) or "-",
            "",
            "Style / Vision",
            f"Vibe: {first('style_vibe')}",
            f"Colors: {first_of('colors', 'colors_love')}",
            f"Inspiration Links: {first_of('references', 'inspiration_links')}",
            f"Inspired Demo: {first('inspired_demo')}",
            "",
            "Existing Assets (multi-select)",
            ", ".join(many("existing_assets[]")) or "-",
            "",
            f"Timeline: {first('timeline')}",
            f"Budget: {first('budget')}",
            f"Additional Notes: {first_of('final_notes', 'additional_details')}",
            f"Referral Source: {first('referral_source')}",
            f"Referral Name: {first('referral_name')}",
            "",
            "Uploaded File Names",
        ]
        file_names = many("inspiration_files_names[]")
        lines.extend(file_names if file_names else ["-"])

        message = EmailMessage()
        message["Subject"] = f"New Inquiry: {first('full_name') or 'Website Lead'}"
        message["From"] = smtp_from
        message["To"] = inquiry_to
        if first("email"):
            message["Reply-To"] = first("email")
        message.set_content("\n".join(lines))

        if use_ssl:
            with smtplib.SMTP_SSL(smtp_host, smtp_port, context=ssl.create_default_context()) as server:
                server.login(smtp_user, smtp_pass)
                server.send_message(message)
        else:
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.ehlo()
                server.starttls(context=ssl.create_default_context())
                server.ehlo()
                server.login(smtp_user, smtp_pass)
                server.send_message(message)

    def _send_testimonial_email(self, fields):
        smtp_host = os.getenv("HOV_SMTP_HOST")
        smtp_port = int(os.getenv("HOV_SMTP_PORT", "587"))
        smtp_user = os.getenv("HOV_SMTP_USER")
        smtp_pass = os.getenv("HOV_SMTP_PASS")
        smtp_from = os.getenv("HOV_SMTP_FROM", smtp_user or "")
        testimonial_to = os.getenv("HOV_TESTIMONIAL_TO", os.getenv("HOV_INQUIRY_TO"))
        use_ssl = os.getenv("HOV_SMTP_SSL", "false").lower() in {"1", "true", "yes"}

        missing = [
            name
            for name, value in [
                ("HOV_SMTP_HOST", smtp_host),
                ("HOV_SMTP_USER", smtp_user),
                ("HOV_SMTP_PASS", smtp_pass),
                ("HOV_SMTP_FROM", smtp_from),
                ("HOV_INQUIRY_TO or HOV_TESTIMONIAL_TO", testimonial_to),
            ]
            if not value
        ]
        if missing:
            raise RuntimeError(f"Missing email env vars: {', '.join(missing)}")

        def first(name):
            values = fields.get(name, [])
            return values[0].strip() if values else ""

        lines = [
            "New House of Visuals Testimonial Submission",
            "",
            "This testimonial has not been published automatically. Review and approve before using publicly.",
            "",
            "Client Info",
            f"Full Name: {first('full_name')}",
            f"Business Name: {first('business_name')}",
            f"Website/Social Link: {first('website_social_link') or '-'}",
            "",
            "Testimonial Details",
            f"Division: {first('testimonial_division') or 'House of Visuals'}",
            f"Service Received: {first('service_received')}",
            f"Star Rating: {first('star_rating')} / 5",
            f"Permission Granted: {first('permission') or 'No'}",
            "",
            "Message",
            first("testimonial_message"),
        ]

        message = EmailMessage()
        division = first("testimonial_division") or "House of Visuals"
        message["Subject"] = f"New {division} Testimonial: {first('full_name') or 'Website Submission'}"
        message["From"] = smtp_from
        message["To"] = testimonial_to
        message.set_content("\n".join(lines))

        if use_ssl:
            with smtplib.SMTP_SSL(smtp_host, smtp_port, context=ssl.create_default_context()) as server:
                server.login(smtp_user, smtp_pass)
                server.send_message(message)
        else:
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.ehlo()
                server.starttls(context=ssl.create_default_context())
                server.ehlo()
                server.login(smtp_user, smtp_pass)
                server.send_message(message)

    def _send_client_feedback_email(self, fields):
        smtp_host = os.getenv("HOV_SMTP_HOST")
        smtp_port = int(os.getenv("HOV_SMTP_PORT", "587"))
        smtp_user = os.getenv("HOV_SMTP_USER")
        smtp_pass = os.getenv("HOV_SMTP_PASS")
        smtp_from = os.getenv("HOV_SMTP_FROM", smtp_user or "")
        feedback_to = os.getenv("HOV_FEEDBACK_TO", os.getenv("HOV_INQUIRY_TO"))
        use_ssl = os.getenv("HOV_SMTP_SSL", "false").lower() in {"1", "true", "yes"}

        missing = [
            name
            for name, value in [
                ("HOV_SMTP_HOST", smtp_host),
                ("HOV_SMTP_USER", smtp_user),
                ("HOV_SMTP_PASS", smtp_pass),
                ("HOV_SMTP_FROM", smtp_from),
                ("HOV_INQUIRY_TO or HOV_FEEDBACK_TO", feedback_to),
            ]
            if not value
        ]
        if missing:
            raise RuntimeError(f"Missing email env vars: {', '.join(missing)}")

        def first(name):
            values = fields.get(name, [])
            return values[0].strip() if values else ""

        lines = [
            "New Client Preview Feedback",
            "",
            "Project",
            f"Client Preview: {first('client_project') or 'Creative Impressions Media'}",
            "",
            "Contact Info",
            f"Name: {first('full_name')}",
            f"Email: {first('email')}",
            "",
            "Feedback Details",
            f"Page: {first('page_name') or '-'}",
            "",
            "Requested Changes / Notes",
            first("feedback_message") or "-",
        ]

        message = EmailMessage()
        message["Subject"] = f"Website Preview Feedback: {first('client_project') or 'Creative Impressions Media'}"
        message["From"] = smtp_from
        message["To"] = feedback_to
        if first("email"):
            message["Reply-To"] = first("email")
        message.set_content("\n".join(lines))

        if use_ssl:
            with smtplib.SMTP_SSL(smtp_host, smtp_port, context=ssl.create_default_context()) as server:
                server.login(smtp_user, smtp_pass)
                server.send_message(message)
        else:
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.ehlo()
                server.starttls(context=ssl.create_default_context())
                server.ehlo()
                server.login(smtp_user, smtp_pass)
                server.send_message(message)


    def do_POST(self):
        request_path = self.path.split("?", 1)[0]

        if request_path == "/admin/upwork-scout/save":
            if not self._admin_allowed():
                self._send_admin_login_required()
                return
            try:
                content_length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(content_length).decode("utf-8", errors="replace")
                fields = parse_qs(raw, keep_blank_values=True)

                pasted_text = first(fields, "pasted_text")
                job_url = first(fields, "job_url")
                status = first(fields, "status") or "New"
                connects_spent = first(fields, "connects_spent")
                notes = first(fields, "notes")

                analyzed = self._analyze_single_upwork_job(pasted_text)
                create_upwork_scout_job(
                    analyzed,
                    job_url=job_url,
                    status=status,
                    notes=notes,
                    connects_spent=connects_spent,
                )

                self.send_response(303)
                self.send_header("Location", "/admin/upwork-scout?saved=1")
                self.end_headers()
            except Exception as error:
                self._send_html(
                    self._admin_shell(
                        "Upwork Scout Save Error",
                        f"<section class='panel'><h1>Save Error</h1><p>{escape(str(error))}</p><a class='btn-small' href='/admin/upwork-scout'>Back to Upwork Scout</a></section>",
                    ),
                    status=400,
                )
            return

        if request_path == "/admin/upwork-scout/analyze":
            if not self._admin_allowed():
                self._send_admin_login_required()
                return
            try:
                content_length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(content_length).decode("utf-8", errors="replace")
                fields = parse_qs(raw, keep_blank_values=True)
                pasted_text = first(fields, "upwork_text")
                results = self._analyze_upwork_jobs(pasted_text)
                self._send_html(self._render_upwork_scout(results=results, pasted_text=pasted_text))
            except Exception as error:
                self._send_html(
                    self._admin_shell(
                        "Upwork Scout Error",
                        f"<section class='panel'><h1>Upwork Scout Error</h1><p>{escape(str(error))}</p><a class='btn-small' href='/admin/upwork-scout'>Back to Upwork Scout</a></section>",
                    ),
                    status=400,
                )
            return

        if request_path == "/admin/research":
            if not self._admin_allowed():
                self._send_admin_login_required()
                return
            try:
                content_length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(content_length).decode("utf-8", errors="replace")
                fields = parse_qs(raw, keep_blank_values=True)

                industry = first(fields, "industry")
                location = first(fields, "location")
                search_query = first(fields, "search_query")
                suggested_offer = many_offer_values(fields)
                recommended_demo = first(fields, "recommended_demo")

                if search_query and location:
                    location_lower = location.lower()
                    query_lower = search_query.lower()

                    if location_lower not in query_lower:
                        search_query = f"{search_query} in {location}".strip()
                elif not search_query:
                    search_query = " ".join(
                        part for part in [industry, "in", location] if part
                    ).strip()

                if not search_query:
                    raise RuntimeError("Enter a search query, or enter both industry and location.")

                print(f"Google Places search query: {search_query}")

                places = search_google_places_text(
                    search_query,
                    first(fields, "max_results") or 10,
                )

                print(f"Google Places returned: {len(places)} places")
                target_mode = first(fields, "target_mode") or "needs_help"
                min_score = first(fields, "min_score") or 0

                result = import_places_as_prospects(
                    places,
                    industry or search_query,
                    suggested_offer,
                    recommended_demo,
                    target_mode=target_mode,
                    min_score=min_score,
                )
                self._send_html(self._render_research_helper(result, fields))
            except Exception as error:
                self._send_html(
                    self._render_research_helper(
                        {"imported": 0, "skipped": 0, "errors": [str(error)]},
                        fields if "fields" in locals() else {},
                    ),
                    status=400,
                )
            return

        if request_path == "/admin/login":
            content_length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(content_length).decode("utf-8", errors="replace")
            fields = parse_qs(raw, keep_blank_values=True)

            token = os.getenv("HOV_ADMIN_TOKEN", "")
            password = first(fields, "password")
            next_path = first(fields, "next") or "/admin"

            if token and hmac.compare_digest(password, token):
                self.send_response(303)
                self.send_header("Set-Cookie", f"hov_admin_session={self._admin_session_signature()}; Path=/admin; HttpOnly; SameSite=Lax")
                self.send_header("Location", next_path)
                self.end_headers()
                return

            self._send_admin_login_required("Incorrect admin password. Please try again.", status=403)
            return

        if request_path.startswith("/admin/prospects/") and request_path.endswith("/mark-contacted"):
            if not self._admin_allowed():
                self._send_admin_login_required()
                return
            try:
                prospect_id = int(request_path.rstrip("/").split("/")[-2])
                content_length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(content_length).decode("utf-8", errors="replace")
                fields = parse_qs(raw, keep_blank_values=True)

                log_prospect_contact(
                    prospect_id=prospect_id,
                    activity_type="Initial Contact",
                    contact_method=first(fields, "contact_method"),
                    follow_up_days=3,
                    notes=first(fields, "contact_notes"),
                )

                self.send_response(303)
                self.send_header("Location", f"/admin/prospects/{prospect_id}")
                self.end_headers()
            except Exception as error:
                self._send_json({"ok": False, "message": str(error)}, status=400)
            return

        if request_path.startswith("/admin/prospects/") and request_path.endswith("/follow-up"):
            if not self._admin_allowed():
                self._send_admin_login_required()
                return
            try:
                prospect_id = int(request_path.rstrip("/").split("/")[-2])
                prospect = get_prospect(prospect_id)

                if not prospect:
                    raise ValueError("Prospect not found.")

                contact_method = prospect.get("last_contact_method")
                if not contact_method:
                    raise ValueError(
                        "Mark this prospect as Contacted before logging the final follow-up."
                    )

                log_prospect_contact(
                    prospect_id=prospect_id,
                    activity_type="Follow-Up",
                    contact_method=contact_method,
                    follow_up_days=4,
                    notes="Final follow-up sent using the original contact method.",
                )

                self.send_response(303)
                self.send_header("Location", f"/admin/prospects/{prospect_id}")
                self.end_headers()
            except Exception as error:
                self._send_json({"ok": False, "message": str(error)}, status=400)
            return

        if request_path.startswith("/admin/prospects/") and request_path.endswith("/no-response"):
            if not self._admin_allowed():
                self._send_admin_login_required()
                return
            try:
                prospect_id = int(request_path.rstrip("/").split("/")[-2])
                mark_prospect_no_response(prospect_id)

                self.send_response(303)
                self.send_header("Location", f"/admin/prospects/{prospect_id}")
                self.end_headers()
            except Exception as error:
                self._send_json({"ok": False, "message": str(error)}, status=400)
            return

        if request_path.startswith("/admin/prospects/") and request_path.endswith("/delete"):
            if not self._admin_allowed():
                self._send_admin_login_required()
                return
            try:
                prospect_id = int(request_path.rstrip("/").split("/")[-2])
                delete_prospect(prospect_id)
                self.send_response(303)
                self.send_header("Location", "/admin/prospects")
                self.end_headers()
            except Exception as error:
                self._send_json({"ok": False, "message": str(error)}, status=400)
            return

        if request_path == "/admin/prospects/import":
            if not self._admin_allowed():
                self._send_admin_login_required()
                return
            try:
                content_length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(content_length).decode("utf-8", errors="replace")
                fields = parse_qs(raw, keep_blank_values=True)
                result = import_prospects_from_csv(first(fields, "csv_data"))
                self._send_html(self._render_prospects_import(result))
            except Exception as error:
                self._send_json({"ok": False, "message": str(error)}, status=400)
            return

        if request_path == "/admin/prospects/import":
            if not self._admin_allowed():
                self._send_admin_login_required()
                return
            self._send_html(self._render_prospects_import())
            return

        if request_path == "/admin/prospects/new":
            if not self._admin_allowed():
                self._send_admin_login_required()
                return
            try:
                content_length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(content_length).decode("utf-8", errors="replace")
                fields = parse_qs(raw, keep_blank_values=True)
                prospect_id = create_prospect(fields)
                self.send_response(303)
                self.send_header("Location", f"/admin/prospects/{prospect_id}")
                self.end_headers()
            except Exception as error:
                self._send_json({"ok": False, "message": str(error)}, status=400)
            return

        if request_path.startswith("/admin/prospects/"):
            if not self._admin_allowed():
                self._send_admin_login_required()
                return
            try:
                prospect_id = int(request_path.rstrip("/").rsplit("/", 1)[-1])
                content_length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(content_length).decode("utf-8", errors="replace")
                fields = parse_qs(raw, keep_blank_values=True)
                update_prospect(prospect_id, fields)
                self.send_response(303)
                self.send_header("Location", f"/admin/prospects/{prospect_id}")
                self.end_headers()
            except Exception as error:
                self._send_json({"ok": False, "message": str(error)}, status=400)
            return

        if request_path.startswith("/admin/leads/") and request_path.endswith("/delete"):
            if not self._admin_allowed():
                self._send_admin_login_required()
                return
            try:
                lead_id = int(request_path.rstrip("/").split("/")[-2])
                delete_lead(lead_id)
                self.send_response(303)
                self.send_header("Location", "/admin")
                self.end_headers()
            except Exception as error:
                self._send_json({"ok": False, "message": str(error)}, status=400)
            return

        if request_path.startswith("/admin/leads/"):
            if not self._admin_allowed():
                self._send_admin_login_required()
                return
            try:
                lead_id = int(request_path.rstrip("/").rsplit("/", 1)[-1])
                content_length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(content_length).decode("utf-8", errors="replace")
                fields = parse_qs(raw, keep_blank_values=True)
                update_lead(lead_id, first(fields, "status"), first(fields, "internal_notes"))
                self.send_response(303)
                self.send_header("Location", f"/admin/leads/{lead_id}")
                self.end_headers()
            except Exception as error:
                self._send_json({"ok": False, "message": str(error)}, status=400)
            return

        if (
            request_path not in {
                "/api/inquiry",
                "/api/testimonial",
                "/api/leads/update",
                "/api/client-feedback",
                "/admin/client-previews/new",
                "/admin/client-previews/deactivate",
                "/admin/client-previews/delete",
            }
            and not (
                request_path.startswith("/admin/client-previews/")
                and request_path.endswith("/edit")
            )
        ):
            self._send_json({"ok": False, "message": "Not found."}, status=404)
            return

        content_type = self.headers.get("Content-Type", "")
        if "application/x-www-form-urlencoded" not in content_type:
            self._send_json(
                {"ok": False, "message": "Unsupported content type. Please submit from the website form."},
                status=415,
            )
            return

        fields = {}
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(content_length).decode("utf-8", errors="replace")
            fields = parse_qs(raw, keep_blank_values=True)
            if request_path == "/api/leads/update":
                if not self._admin_allowed():
                    self._send_json({"ok": False, "message": "Admin access required."}, status=403)
                    return
                lead_id = int(first(fields, "lead_id"))
                update_lead(lead_id, first(fields, "status"), first(fields, "internal_notes"))
                self._send_json({"ok": True, "message": "Lead updated successfully."}, status=200)
                return

            if request_path == "/api/testimonial":
                self._send_testimonial_email(fields)
                self._send_json(
                    {
                        "ok": True,
                        "message": "Thank you for sharing your experience. We’ll review your testimonial before publishing.",
                    },
                    status=200,
                )
                return

            if request_path == "/api/client-feedback":
                self._send_client_feedback_email(fields)

                client_slug_values = fields.get("client_slug", [])
                client_slug = client_slug_values[0].strip() if client_slug_values else "creative-impressions"
                client_slug = re.sub(r"[^a-z0-9-]", "", client_slug.lower()) or "creative-impressions"

                self.send_response(303)
                self.send_header("Location", f"/client-preview/{client_slug}/thank-you")
                self.end_headers()
                return

            if request_path == "/admin/client-previews/new":
                if not self._admin_allowed():
                    self._send_json({"ok": False, "message": "Admin access required."}, status=403)
                    return
                create_client_preview(fields)
                self.send_response(303)
                self.send_header("Location", "/admin/client-previews")
                self.end_headers()
                return

            if request_path == "/admin/client-previews/deactivate":
                if not self._admin_allowed():
                    self._send_json({"ok": False, "message": "Admin access required."}, status=403)
                    return
                preview_id = int(first(fields, "preview_id"))
                deactivate_client_preview(preview_id)
                self.send_response(303)
                self.send_header("Location", "/admin/client-previews")
                self.end_headers()
                return

            if request_path.startswith("/admin/client-previews/") and request_path.endswith("/edit"):
                if not self._admin_allowed():
                    self._send_json({"ok": False, "message": "Admin access required."}, status=403)
                    return

                try:
                    preview_id = int(request_path.split("/")[-2])
                except (TypeError, ValueError):
                    self._send_json(
                        {"ok": False, "message": "Invalid client preview."},
                        status=400,
                    )
                    return

                update_client_preview(preview_id, fields)

                self.send_response(303)
                self.send_header("Location", "/admin/client-previews")
                self.end_headers()
                return

            if request_path == "/admin/client-previews/delete":
                if not self._admin_allowed():
                    self._send_json({"ok": False, "message": "Admin access required."}, status=403)
                    return
                preview_id = int(first(fields, "preview_id"))
                delete_client_preview(preview_id)
                self.send_response(303)
                self.send_header("Location", "/admin/client-previews")
                self.end_headers()
                return

            lead_id = create_lead(fields)
            self._send_inquiry_email(fields)
            update_lead_email_status(lead_id, "sent")
            self._send_json(
                {"ok": True, "message": "Inquiry sent successfully.", "lead_id": lead_id},
                status=200,
            )
        except Exception as error:
            if request_path == "/api/inquiry" and "lead_id" in locals():
                update_lead_email_status(lead_id, "failed", str(error))

            if "Missing email env vars" in str(error):
                if request_path == "/api/testimonial":
                    output_path = self._save_testimonial_locally(fields, str(error))
                    self._send_json(
                        {
                            "ok": True,
                            "message": "Thank you for sharing your experience. We’ll review your testimonial before publishing.",
                            "saved_to": str(output_path),
                        },
                        status=200,
                    )
                    return

                output_path = self._save_inquiry_locally(fields, str(error))
                saved_lead_id = locals().get("lead_id")
                self._send_json(
                    {
                        "ok": True,
                        "message": "Inquiry saved as a lead. Email delivery still needs to be configured.",
                        "saved_to": str(output_path),
                        "lead_id": saved_lead_id,
                    },
                    status=200,
                )
                return

            self._send_json(
                {
                    "ok": False,
                    "message": "We could not send your testimonial right now. Please try again."
                    if request_path == "/api/testimonial"
                    else "We could not send your inquiry right now. Please try again.",
                    "error": str(error),
                },
                status=500,
            )

    def do_GET(self):
        request_path = self.path.split("?", 1)[0]

        if request_path == "/admin/research":
            if not self._admin_allowed():
                self._send_admin_login_required()
                return
            self._send_html(self._render_research_helper())
            return

        if request_path in {"/admin/upwork-scout", "/admin/upwork-scout/"}:
            if not self._admin_allowed():
                self._send_admin_login_required()
                return
            self._send_html(self._render_upwork_scout())
            return

        if request_path in {"/admin/client-previews", "/admin/client-previews/"}:
            if not self._admin_allowed():
                self._send_admin_login_required()
                return
            self._render_client_previews()
            return

        if request_path in {"/admin/client-previews/new", "/admin/client-previews/new/"}:
            if not self._admin_allowed():
                self._send_admin_login_required()
                return
            self._render_client_preview_form()
            return

        if request_path.startswith("/admin/client-previews/") and request_path.endswith("/edit"):
            if not self._admin_allowed():
                self._send_admin_login_required()
                return

            try:
                preview_id = int(request_path.split("/")[-2])
            except (TypeError, ValueError):
                self._send_html(
                    self._admin_shell(
                        "Invalid Client Preview",
                        "<section class='panel'><h1>Invalid client preview.</h1></section>",
                    ),
                    status=400,
                )
                return

            self._render_client_preview_edit_form(preview_id)
            return

        if request_path == "/admin/login":
            self._send_admin_login_required(status=200)
            return

        if request_path == "/admin/logout":
            self.send_response(303)
            self.send_header("Set-Cookie", "hov_admin_session=; Path=/admin; Max-Age=0; HttpOnly; SameSite=Lax")
            self.send_header("Set-Cookie", "hov_admin_session=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax")
            self.send_header("Location", "/admin/login")
            self.end_headers()
            return

        if request_path == "/admin/leads/export":
            if not self._admin_allowed():
                self._send_admin_login_required()
                return
            self._export_leads_csv(completed_only=False)
            return

        if request_path == "/admin/prospects/export":
            if not self._admin_allowed():
                self._send_admin_login_required()
                return
            self._export_prospects_csv()
            return

        if request_path in {"/admin/completed", "/admin/completed/"}:
            if not self._admin_allowed():
                self._send_admin_login_required()
                return
            self._send_html(self._render_completed_projects())
            return

        if request_path == "/admin/completed/export":
            if not self._admin_allowed():
                self._send_admin_login_required()
                return
            self._export_leads_csv(completed_only=True)
            return

        if request_path in {"/admin/prospects", "/admin/prospects/"}:
            if not self._admin_allowed():
                self._send_admin_login_required()
                return
            self._send_html(self._render_prospects_dashboard())
            return

        if request_path == "/admin/prospects/import":
            if not self._admin_allowed():
                self._send_admin_login_required()
                return
            self._send_html(self._render_prospects_import())
            return

        if request_path == "/admin/prospects/new":
            if not self._admin_allowed():
                self._send_admin_login_required()
                return
            self._send_html(self._render_prospect_form())
            return

        if request_path.startswith("/admin/prospects/"):
            if not self._admin_allowed():
                self._send_admin_login_required()
                return
            try:
                prospect_id = int(request_path.rstrip("/").rsplit("/", 1)[-1])
            except ValueError:
                self._send_html(self._admin_shell("Invalid Prospect", "<section class='panel'><h1>Invalid prospect id.</h1></section>"), status=400)
                return
            prospect = get_prospect(prospect_id)
            if not prospect:
                self._send_html(self._admin_shell("Prospect Not Found", "<section class='panel'><h1>Prospect not found.</h1><a href='/admin/prospects'>Back to prospects</a></section>"), status=404)
                return
            self._send_html(self._render_prospect_form(prospect))
            return

        if request_path == "/api/leads":
            if not self._admin_allowed():
                self._send_json({"ok": False, "message": "Admin access required."}, status=403)
                return
            self._send_json({"ok": True, "leads": get_leads(), "statuses": DEFAULT_LEAD_STATUSES}, status=200)
            return

        if request_path.startswith("/api/leads/"):
            if not self._admin_allowed():
                self._send_json({"ok": False, "message": "Admin access required."}, status=403)
                return
            try:
                lead_id = int(request_path.rstrip("/").rsplit("/", 1)[-1])
            except ValueError:
                self._send_json({"ok": False, "message": "Invalid lead id."}, status=400)
                return
            lead = get_lead(lead_id)
            if not lead:
                self._send_json({"ok": False, "message": "Lead not found."}, status=404)
                return
            self._send_json({"ok": True, "lead": lead, "statuses": DEFAULT_LEAD_STATUSES}, status=200)
            return

        if request_path in {"/admin", "/admin/"}:
            if not self._admin_allowed():
                self._send_admin_login_required()
                return
            self._send_html(self._render_admin_overview())
            return

        if request_path in {"/admin/leads", "/admin/leads/"}:
            if not self._admin_allowed():
                self._send_admin_login_required()
                return
            self._send_html(self._render_leads_dashboard())
            return

        if request_path.startswith("/admin/leads/"):
            if not self._admin_allowed():
                self._send_admin_login_required()
                return
            try:
                lead_id = int(request_path.rstrip("/").rsplit("/", 1)[-1])
            except ValueError:
                self._send_html(self._admin_shell("Invalid Lead", "<section class='panel'><h1>Invalid lead id.</h1></section>"), status=400)
                return
            self._render_lead_detail(lead_id)
            return

        if request_path in {"/client-preview/jukebox-lounge", "/client-preview/jukebox-lounge/"}:
            self._render_client_preview_landing_page(
                "client-preview-jukebox-lounge.html",
                "jukebox-lounge",
            )
            return

        if request_path in {"/client-preview/jukebox-lounge/feedback", "/client-preview/jukebox-lounge/feedback/"}:
            self.path = "/client-preview-jukebox-lounge-feedback.html"

        if request_path in {"/client-preview/jukebox-lounge/thank-you", "/client-preview/jukebox-lounge/thank-you/"}:
            self.path = "/client-preview-jukebox-lounge-thank-you.html"

        if request_path in {"/client-preview/creative-impressions", "/client-preview/creative-impressions/"}:
            self._render_client_preview_landing_page(
                "client-preview-creative-impressions.html",
                "creative-impressions",
            )
            return

        if request_path in {"/client-preview/creative-impressions/feedback", "/client-preview/creative-impressions/feedback/"}:
            self.path = "/client-preview-creative-impressions-feedback.html"

        if request_path in {"/client-preview/creative-impressions/thank-you", "/client-preview/creative-impressions/thank-you/"}:
            self.path = "/client-preview-creative-impressions-thank-you.html"



        # Automatically serve future client preview landing pages.
        preview_parts = [
            part
            for part in request_path.strip("/").split("/")
            if part
        ]

        if len(preview_parts) >= 2 and preview_parts[0] == "client-preview":
            client_slug = preview_parts[1]

            if len(preview_parts) == 2:
                preview_filename = f"client-preview-{client_slug}.html"
                preview_file = PROJECT_DIR / preview_filename

                if preview_file.exists():
                    self._render_client_preview_landing_page(
                        preview_filename,
                        client_slug,
                    )
                    return

            if len(preview_parts) == 3 and preview_parts[2] in {"feedback", "thank-you"}:
                page_type = preview_parts[2]
                page_filename = f"client-preview-{client_slug}-{page_type}.html"
                page_file = PROJECT_DIR / page_filename

                if page_file.exists():
                    self.path = f"/{page_filename}"

        # Common convenience routes.
        if request_path in {"/", ""}:
            self.path = "/index.html"
        elif request_path.endswith("/") and request_path != "/":
            # Support both:
            # /page/ -> /page.html
            # /nested/page/ -> /nested/page/index.html
            page_name = request_path.strip("/")
            html_candidate = PROJECT_DIR / f"{page_name}.html"
            index_candidate = PROJECT_DIR / page_name / "index.html"

            if html_candidate.exists():
                self.path = f"/{page_name}.html"
            elif index_candidate.exists():
                self.path = f"/{page_name}/index.html"
        elif request_path != "/" and "." not in request_path.rsplit("/", 1)[-1]:
            # Support non-trailing-slash nested routes, e.g. /live-demos/realtor
            page_name = request_path.strip("/")
            index_candidate = PROJECT_DIR / page_name / "index.html"
            html_candidate = PROJECT_DIR / f"{page_name}.html"

            if index_candidate.exists():
                self.path = f"/{page_name}/index.html"
            elif html_candidate.exists():
                self.path = f"/{page_name}.html"

        return super().do_GET()

    def log_message(self, format, *args):
        # Keep logs readable while developing locally.
        print(f"[server] {self.address_string()} - {format % args}")


def main():
    parser = argparse.ArgumentParser(description="Run House of Visuals local server.")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind (default: 8000)")
    args = parser.parse_args()

    os.chdir(PROJECT_DIR)
    init_database()

    server = ThreadingHTTPServer((args.host, args.port), SiteHandler)
    print(f"Serving House of Visuals at http://{args.host}:{args.port}")
    print(f"Project directory: {PROJECT_DIR}")
    print("Press Ctrl+C to stop.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
