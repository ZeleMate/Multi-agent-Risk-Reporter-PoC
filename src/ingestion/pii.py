import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


class PIIRedactor:
    """PII redaction utility for emails and names."""

    def __init__(self, known_people: dict[str, dict[str, str]] | None = None):
        # Basic patterns for PoC
        self.email_pattern = re.compile(r"[^<>\s()]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
        self.phone_pattern = re.compile(r"(\+36|06)?[\s-]?(\d{1,2})[\s-]?(\d{3})[\s-]?(\d{3,4})")

        # Known people for name redaction
        self.known_people = known_people or {}
        self._known_names_regex = None
        if self.known_people:
            try:
                names = [re.escape(person.get("name", "")) for person in self.known_people.values() if person.get("name")]
                if names:
                    self._known_names_regex = re.compile("|".join(sorted(names, key=len, reverse=True)))
            except Exception:
                pass

    def redact_text(self, text: str) -> str:
        """Redact PII from text."""
        if not text:
            return text

        redacted = text

        # Redact emails and phone numbers
        redacted = self.email_pattern.sub("[EMAIL]", redacted)
        redacted = self.phone_pattern.sub("[PHONE]", redacted)

        # Redact known names
        if self._known_names_regex:
            redacted = self._known_names_regex.sub("[NAME]", redacted)

        return redacted

    def redact_email_data(self, email_data: dict[str, Any]) -> dict[str, Any]:
        """Redact PII from email data."""
        redacted = email_data.copy()

        # Redact sender info
        if "sender_email" in redacted:
            redacted["sender_email"] = "[EMAIL]"
            original_email = email_data.get("sender_email")
            if original_email and original_email in self.known_people:
                person_id = self.known_people[original_email].get("person_id", "[NAME]")
                redacted["sender_name"] = person_id
                redacted["sender_person_id"] = person_id
            else:
                redacted["sender_name"] = "[NAME]"
                redacted["sender_person_id"] = "[PERSON]"

        # Redact recipients
        for recipient_list in ["to_recipients", "cc_recipients"]:
            if recipient_list in redacted:
                for recipient in redacted[recipient_list]:
                    original_email = recipient.get("email")
                    if original_email and original_email in self.known_people:
                        person_id = self.known_people[original_email].get("person_id", "[NAME]")
                        recipient["name"] = person_id
                        recipient["person_id"] = person_id
                    else:
                        recipient["name"] = "[NAME]"
                    if "email" in recipient:
                        recipient["email"] = "[EMAIL]"

        # Redact text fields
        for field in ["subject", "canonical_subject", "body"]:
            if field in redacted and redacted[field]:
                redacted[field] = self.redact_text(redacted[field])

        return redacted

    def redact_thread_data(self, thread_data: dict[str, Any]) -> dict[str, Any]:
        """Redact PII from thread data."""
        redacted = thread_data.copy()

        # Redact participants
        if "participants" in redacted:
            redacted["participants"] = ["[EMAIL]" for _ in redacted["participants"]]

        # Redact emails
        if "emails" in redacted:
            redacted["emails"] = [self.redact_email_data(email) for email in redacted["emails"]]

        return redacted


def redact_pii_from_text(text: str) -> str:
    """Convenience function to redact PII from text."""
    redactor = PIIRedactor()
    return redactor.redact_text(text)


def redact_pii_from_data(data: dict[str, Any]) -> dict[str, Any]:
    """Convenience function to redact PII from data."""
    redactor = PIIRedactor()
    return redactor.redact_thread_data(data)
