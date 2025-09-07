import json
import logging
import os
import re
from datetime import datetime
from typing import Any

from src.ingestion.chunker import create_chunks
from src.ingestion.pii import PIIRedactor
from src.services.config import get_config

logger = logging.getLogger(__name__)

# Note: logging configuration is handled by the CLI entrypoint; avoid setting it at import time here.


def normalize_date(date_str: str) -> dict[str, Any]:
    """Normalize hungarian date string and return epoch timestamp."""
    try:
        dt = datetime.strptime(date_str, "%Y.%m.%d %H:%M")
        return {"normalized_date": dt.isoformat(), "epoch_timestamp": int(dt.timestamp())}
    except Exception as e:
        logger.debug(f"Date parsing failed for '{date_str}': {e}")
        return {"normalized_date": date_str, "epoch_timestamp": None}


def parse_colleagues(colleagues_path: str) -> dict[str, dict[str, str]]:
    """Parse the colleagues.txt file."""
    colleagues = {}
    try:
        with open(colleagues_path, encoding="utf-8") as file:
            for line in file:
                line = line.strip()
                if not line or line.startswith("Characters:"):
                    continue

                match = re.match(r"(.+?):\s*(.+?)\s*\((.+?)\)", line)
                if match:
                    role, name, email = match.groups()
                    colleagues[email] = {
                        "name": name.strip(),
                        "role": role.strip(),
                        "email": email.strip(),
                    }

        return colleagues

    except Exception as e:
        logger.error(f"Error parsing colleagues file {colleagues_path}: {e}")
        return {}


def parse_email_thread(
    email_path: str, colleagues: dict[str, dict[str, str]], redactor: PIIRedactor
) -> dict[str, Any]:
    """Parse an email thread file."""
    try:
        with open(email_path, encoding="utf-8") as file:
            content = file.read()

        # Split content into individual emails
        email_matches: list[str] = []
        lines = content.split("\n")
        current_email: list[str] = []

        for line in lines:
            if line.startswith("From:"):
                if current_email:
                    email_matches.append("\n".join(current_email))
                current_email = [line]
            elif current_email:
                current_email.append(line)

        if current_email:
            email_matches.append("\n".join(current_email))

        emails = []
        for email_content in email_matches:
            email_content = email_content.strip()
            if not email_content:
                continue

            # Parse individual email
            email_data = parse_single_email(email_content, colleagues, redactor)
            if email_data:
                emails.append(email_data)

        # Create thread summary with simple thread_id
        if emails:
            canonical_subject = emails[0].get("canonical_subject", "")
            thread_id = f"thread_{canonical_subject}_{len(emails)}"
        else:
            thread_id = os.path.basename(email_path).replace(".txt", "")

        # Participants based on sender_person_id
        participants_redacted = list({em.get("sender_person_id", "[PERSON]") for em in emails})

        thread_data = {
            "thread_id": thread_id,
            "file_path": email_path,
            "total_emails": len(emails),
            "participants": participants_redacted,
            "subject": emails[0]["subject"] if emails else "",
            "canonical_subject": emails[0].get("canonical_subject", "") if emails else "",
            "start_date": emails[0]["date"] if emails else "",
            "end_date": emails[-1]["date"] if emails else "",
            "emails": emails,
        }

        return thread_data

    except Exception as e:
        logger.error(f"Error parsing email thread {email_path}: {e}")
        return {}


def parse_single_email(
    email_content: str, colleagues: dict[str, dict[str, str]], redactor: PIIRedactor
) -> dict[str, Any] | None:
    """Parse a single email."""
    try:
        # Extract From field
        from_match = re.search(
            r"From:\s*(.+?)\s*\(([^)]+)\)|"
            + r"From:\s*(.+?)\s*<([^>]+)>|"
            + r"From:\s*(.+?)\s+([^\s]+@[^\s]+)",
            email_content,
        )
        if not from_match:
            logger.warning("Could not parse From line")
            return None

        # Get sender info
        if from_match.group(2):
            sender_info, sender_email = from_match.group(1).strip(), from_match.group(2).strip()
        elif from_match.group(4):
            sender_info, sender_email = from_match.group(3).strip(), from_match.group(4).strip()
        else:
            sender_info, sender_email = from_match.group(5).strip(), from_match.group(6).strip()

        # Extract To and Cc fields
        to_match = re.search(r"To:\s*(.+?)(?:\n|$)", email_content, re.MULTILINE)
        to_recipients = parse_recipients(to_match.group(1).strip()) if to_match else []

        cc_match = re.search(r"Cc:\s*(.+?)(?:\n|$)", email_content, re.MULTILINE)
        cc_recipients = parse_recipients(cc_match.group(1).strip()) if cc_match else []

        # Extract Date and Subject
        date_match = re.search(r"Date:\s*(.+?)(?:\n|$)", email_content, re.MULTILINE)
        date_str = date_match.group(1).strip() if date_match else ""
        date_normalized = (
            normalize_date(date_str)
            if date_str
            else {"normalized_date": "", "epoch_timestamp": None}
        )

        subject_match = re.search(r"Subject:\s*(.+?)(?:\n|$)", email_content, re.MULTILINE)
        subject = subject_match.group(1).strip() if subject_match else ""

        # Extract body (everything after headers)
        lines = email_content.split("\n")
        body_start = next(
            (i + 1 for i, line in enumerate(lines) if line.strip() == "" and i > 0), 0
        )
        body = "\n".join(lines[body_start:]).strip()

        # Get sender info from colleagues
        sender_data = colleagues.get(sender_email, {})
        sender_role = sender_data.get("role", "Unknown")
        sender_name = sender_data.get("name", sender_info.split()[0] if sender_info else "Unknown")

        # Create canonical subject (strip RE:, FW:, etc.)
        canonical_subject = (
            re.sub(r"^(RE:|FW:|FWD:)\s*", "", subject, flags=re.IGNORECASE).strip().lower()
        )

        email_data = {
            "sender_name": sender_name,
            "sender_email": sender_email,
            "sender_role": sender_role,
            "to_recipients": to_recipients,
            "cc_recipients": cc_recipients,
            "date": date_str,
            "date_normalized": date_normalized["normalized_date"],
            "subject": subject,
            "canonical_subject": canonical_subject,
            "body": body,
        }

        # Apply PII redaction
        return redactor.redact_email_data(email_data)

    except Exception as e:
        logger.error(f"Error parsing single email: {e}")
        return None


def parse_recipients(recipients_str: str) -> list[dict[str, str]]:
    """Parse recipients string."""
    if not recipients_str:
        return []

    recipients = []
    for recipient in recipients_str.split(","):
        recipient = recipient.strip()
        if not recipient:
            continue

        email_match = re.search(r"([^<>\s]+@[^\s>]+)", recipient)
        if email_match:
            email = email_match.group(1)
            name = recipient.replace(f"<{email}>", "").replace(email, "").strip()
            recipients.append({"name": name if name else "Unknown", "email": email})

    return recipients


def process_email_data(input_dir: str, output_dir: str) -> None:
    """Process all email threads and colleagues data."""
    try:
        os.makedirs(output_dir, exist_ok=True)

        # Find colleagues file
        colleagues_file = None
        for root, _dirs, files in os.walk(input_dir):
            if "Colleagues.txt" in files:
                colleagues_file = os.path.join(root, "Colleagues.txt")
                break

        if not colleagues_file:
            logger.error("Colleagues.txt not found in input directory")
            return

        colleagues = parse_colleagues(colleagues_file)

        # Create person_id mapping and data structures
        person_data = {}
        for email, data in colleagues.items():
            name_clean = data["name"].lower().replace(" ", "_")
            role_clean = data["role"].lower().replace(" ", "_").replace("(", "").replace(")", "")
            person_id = f"{name_clean}_{role_clean}"

            person_data[email] = {
                "person_id": person_id,
                "name": data["name"],
                "role": data["role"],
                "email_redacted": "[EMAIL]",
            }

        # Build known_people for redactor
        known_people = {
            email: {"person_id": data["person_id"], "name": data["name"], "role": data["role"]}
            for email, data in person_data.items()
        }

        # Save colleagues data (PII protected)
        colleagues_clean = {
            email: {
                "person_id": data["person_id"],
                "role": data["role"],
                "email_redacted": data["email_redacted"],
            }
            for email, data in person_data.items()
        }

        redactor = PIIRedactor(known_people=known_people)

        # Save colleagues data
        with open(os.path.join(output_dir, "colleagues.json"), "w", encoding="utf-8") as f:
            json.dump(colleagues_clean, f, ensure_ascii=False, indent=2)

        # Find and parse email files
        email_files = []
        for root, _dirs, files in os.walk(input_dir):
            for file in files:
                if file.startswith("email") and file.endswith(".txt"):
                    email_files.append(os.path.join(root, file))

        all_threads = []
        for email_file in sorted(email_files):
            thread_data = parse_email_thread(email_file, colleagues, redactor)
            if thread_data:
                all_threads.append(thread_data)

        # Save threads data
        with open(os.path.join(output_dir, "email_threads.json"), "w", encoding="utf-8") as f:
            json.dump(all_threads, f, ensure_ascii=False, indent=2)

        # Create and save chunks
        app_config = get_config()
        chunks = create_chunks(
            all_threads,
            chunk_size=getattr(app_config.chunking, "chunk_size", 1000),
            overlap=getattr(app_config.chunking, "overlap", 100),
        )

        with open(os.path.join(output_dir, "chunks.json"), "w", encoding="utf-8") as f:
            json.dump(chunks, f, ensure_ascii=False, indent=2)

        # Save summary
        summary = {
            "total_threads": len(all_threads),
            "total_emails": sum(thread["total_emails"] for thread in all_threads),
            "total_participants": len(colleagues),
            "date_processed": datetime.now().isoformat(),
        }

        with open(os.path.join(output_dir, "summary.json"), "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        logger.info(f"Processed {len(all_threads)} threads with {summary['total_emails']} emails")

    except Exception as e:
        logger.error(f"Error processing email data: {e}")
        raise


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    app_config = get_config()
    process_email_data(app_config.data_raw, app_config.data_clean)
