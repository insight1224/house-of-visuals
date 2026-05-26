#!/usr/bin/env python3
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import argparse
from datetime import datetime
import json
import os
import smtplib
import ssl
from email.message import EmailMessage
from urllib.parse import parse_qs


PROJECT_DIR = Path(__file__).resolve().parent
INQUIRY_DIR = PROJECT_DIR / "inquiries"
TESTIMONIAL_DIR = PROJECT_DIR / "testimonials"


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


class SiteHandler(SimpleHTTPRequestHandler):
    def _send_json(self, payload, status=200):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

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
            f"Service Received: {first('service_received')}",
            f"Star Rating: {first('star_rating')} / 5",
            f"Permission Granted: {first('permission') or 'No'}",
            "",
            "Message",
            first("testimonial_message"),
        ]

        message = EmailMessage()
        message["Subject"] = f"New Testimonial: {first('full_name') or 'Website Submission'}"
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

    def do_POST(self):
        request_path = self.path.split("?", 1)[0]
        if request_path not in {"/api/inquiry", "/api/testimonial"}:
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

            self._send_inquiry_email(fields)
            self._send_json({"ok": True, "message": "Inquiry sent successfully."}, status=200)
        except Exception as error:
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
                self._send_json(
                    {
                        "ok": True,
                        "message": "Inquiry saved locally. Email delivery still needs to be configured before launch.",
                        "saved_to": str(output_path),
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
