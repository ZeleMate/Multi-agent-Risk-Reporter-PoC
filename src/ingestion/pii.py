import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


class PIIRedactor:
    """
    PII (Personally Identifiable Information) redaction utility.
    Redacts emails, phone numbers, IDs, and other sensitive information.
    """

    def __init__(self, known_people: dict[str, dict[str, str]] | None = None):
        # Email patterns (allow Unicode in local-part; ASCII domain/TLD)
        self.email_pattern = re.compile(r"[^<>\s()]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")

        # Phone number patterns (Hungarian format)
        self.phone_pattern = re.compile(r"(\+36|06)?[\s-]?(\d{1,2})[\s-]?(\d{3})[\s-]?(\d{3,4})")

        # ID patterns (various formats)
        self.id_pattern = re.compile(r"\b\d{6}[A-Z]{2}\d{2}[A-Z]{2}\d{3}\b")  # Hungarian ID
        self.credit_card_pattern = re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b")

        # IP address patterns
        self.ip_pattern = re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")

        # URL patterns (but keep domain names for context)
        self.url_pattern = re.compile(r"https?://[^\s]+")

        # Known people (email -> {person_id, name, role}) for name redaction
        self.known_people = known_people or {}
        # Precompile a regex that matches any known full name (escaped, word boundaries)
        self._known_names_regex = None
        try:
            full_names: list[str] = []
            name_tokens: list[str] = []
            for person in self.known_people.values():
                name = person.get("name")
                if not name:
                    continue
                full_names.append(re.escape(name))
                # Also redact first/last tokens to catch partial mentions
                for token in name.split():
                    if len(token) >= 3:
                        name_tokens.append(re.escape(token))
            patterns: list[str] = []
            if full_names:
                patterns.append("(" + "|".join(sorted(full_names, key=len, reverse=True)) + ")")
            if name_tokens:
                patterns.append(
                    "(" + "|".join(sorted(set(name_tokens), key=len, reverse=True)) + ")"
                )
            if patterns:
                self._known_names_regex = re.compile("|".join(patterns))
        except Exception:
            self._known_names_regex = None

    def redact_text(self, text: str) -> str:
        """
        Redact PII from text while preserving structure.

        Args:
            text: Input text to redact

        Returns:
            Redacted text with PII replaced by placeholders
        """
        if not text:
            return text

        redacted = text

        # Redact emails
        redacted = self.email_pattern.sub("[EMAIL]", redacted)

        # Redact phone numbers
        redacted = self.phone_pattern.sub("[PHONE]", redacted)

        # Redact IDs
        redacted = self.id_pattern.sub("[ID]", redacted)
        redacted = self.credit_card_pattern.sub("[CARD]", redacted)

        # Redact IP addresses
        redacted = self.ip_pattern.sub("[IP]", redacted)

        # Redact URLs (but keep domain context)
        redacted = self.url_pattern.sub("[URL]", redacted)

        # Redact known names from text if available
        if self._known_names_regex is not None:
            redacted = self._known_names_regex.sub("[NAME]", redacted)

        return redacted

    def redact_email_data(self, email_data: dict[str, Any]) -> dict[str, Any]:
        """
        Redact PII from email data structure.

        Args:
            email_data: Email data dictionary

        Returns:
            Redacted email data
        """
        redacted = email_data.copy()

        # Redact sender email
        if "sender_email" in redacted:
            redacted["sender_email"] = "[EMAIL]"
            # Replace sender_name with person_id if known, otherwise generic token
            original_sender_email = email_data.get("sender_email")
            if original_sender_email and original_sender_email in self.known_people:
                person_id = self.known_people[original_sender_email].get("person_id", "[NAME]")
                redacted["sender_name"] = person_id
                redacted["sender_person_id"] = person_id
            else:
                redacted["sender_name"] = "[NAME]"
                redacted["sender_person_id"] = "[PERSON]"

        # Redact recipient emails
        if "to_recipients" in redacted:
            for recipient in redacted["to_recipients"]:
                original_email = recipient.get("email")
                if original_email and original_email in self.known_people:
                    person_id = self.known_people[original_email].get("person_id", "[NAME]")
                    recipient["name"] = person_id
                    recipient["person_id"] = person_id
                else:
                    recipient["name"] = "[NAME]"
                if "email" in recipient:
                    recipient["email"] = "[EMAIL]"

        if "cc_recipients" in redacted:
            for recipient in redacted["cc_recipients"]:
                original_email = recipient.get("email")
                if original_email and original_email in self.known_people:
                    person_id = self.known_people[original_email].get("person_id", "[NAME]")
                    recipient["name"] = person_id
                    recipient["person_id"] = person_id
                else:
                    recipient["name"] = "[NAME]"
                if "email" in recipient:
                    recipient["email"] = "[EMAIL]"

        # Redact subject fields
        if "subject" in redacted and redacted["subject"]:
            redacted["subject"] = self.redact_text(redacted["subject"])
        if "canonical_subject" in redacted and redacted["canonical_subject"]:
            redacted["canonical_subject"] = self.redact_text(redacted["canonical_subject"])

        # Redact body text
        if "body" in redacted:
            redacted["body"] = self.redact_text(redacted["body"])

        return redacted

    def redact_thread_data(self, thread_data: dict[str, Any]) -> dict[str, Any]:
        """
        Redact PII from entire thread data.

        Args:
            thread_data: Thread data dictionary

        Returns:
            Redacted thread data
        """
        redacted = thread_data.copy()

        # Redact participants list
        if "participants" in redacted:
            redacted["participants"] = ["[EMAIL]" for _ in redacted["participants"]]

        # Redact individual emails
        if "emails" in redacted:
            redacted["emails"] = [self.redact_email_data(email) for email in redacted["emails"]]

        return redacted


def redact_pii_from_text(text: str) -> str:
    """
    Convenience function to redact PII from text.

    Args:
        text: Input text

    Returns:
        Redacted text
    """
    redactor = PIIRedactor()
    return redactor.redact_text(text)


def redact_pii_from_data(data: dict[str, Any]) -> dict[str, Any]:
    """
    Convenience function to redact PII from data structure.

    Args:
        data: Data dictionary (thread or email data)

    Returns:
        Redacted data
    """
    redactor = PIIRedactor()
    return redactor.redact_thread_data(data)
