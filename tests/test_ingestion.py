"""
Critical tests for data ingestion and parsing functionality.
Tests the essential parser.py and PII redactor functionality for PoC.
"""

import os

from src.ingestion.parser import (
    normalize_date,
    parse_colleagues,
    parse_recipients,
    parse_single_email,
)
from src.ingestion.pii import PIIRedactor


class TestNormalizeDate:
    """Test critical date normalization functionality."""

    def test_normalize_date_valid_email_format(self):
        """Test normalizing valid email date format."""
        date_str = "2024.01.15 10:30"
        result = normalize_date(date_str)

        assert "normalized_date" in result
        assert "epoch_timestamp" in result
        assert result["normalized_date"].startswith("2024-01-15")
        assert isinstance(result["epoch_timestamp"], int)

    def test_normalize_date_invalid_format(self):
        """Test normalizing invalid date format."""
        date_str = "not a date"
        result = normalize_date(date_str)

        assert result["normalized_date"] == date_str
        assert result["epoch_timestamp"] is None


class TestParseColleagues:
    """Test critical colleagues parsing functionality."""

    def test_parse_colleagues_valid_file(self, temp_dir):
        """Test parsing valid colleagues file."""
        content = """Project Manager (PM): John Smith (john.smith@company.com)
Developer (DEV): Jane Doe (jane.doe@company.com)
"""

        file_path = os.path.join(temp_dir, "Colleagues.txt")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        result = parse_colleagues(file_path)

        assert len(result) == 2
        assert result["john.smith@company.com"]["name"] == "John Smith"
        assert result["john.smith@company.com"]["role"] == "Project Manager (PM)"

    def test_parse_colleagues_missing_file(self):
        """Test parsing non-existent colleagues file."""
        result = parse_colleagues("/nonexistent/path/Colleagues.txt")
        assert result == {}


class TestParseRecipients:
    """Test critical recipients parsing functionality."""

    def test_parse_recipients_single_email(self):
        """Test parsing single email recipient."""
        recipient_str = "John Smith <john.smith@company.com>"
        result = parse_recipients(recipient_str)

        assert len(result) == 1
        assert result[0]["name"] == "John Smith"
        # Parser does not redact PII; PII redaction happens in PIIRedactor
        assert result[0]["email"] == "john.smith@company.com"

    def test_parse_recipients_multiple_emails(self):
        """Test parsing multiple email recipients."""
        recipient_str = "John Smith <john.smith@company.com>, Jane Doe <jane.doe@company.com>"
        result = parse_recipients(recipient_str)

        assert len(result) == 2
        assert result[0]["name"] == "John Smith"
        assert result[1]["name"] == "Jane Doe"

    def test_parse_single_email_valid_format(self):
        """Test parsing valid email format."""
        email_content = """From: John Smith <john.smith@company.com>
To: Jane Doe <jane.doe@company.com>
Date: 2024.01.15 10:30
Subject: Test Subject

This is the email body content.
"""

        colleagues = {"john.smith@company.com": {"name": "John Smith", "role": "Developer"}}

        # Create redactor with proper known people for testing
        known_people = {
            "john.smith@company.com": {
                "person_id": "john_smith_developer",
                "name": "John Smith",
                "role": "Developer",
            }
        }
        redactor = PIIRedactor(known_people=known_people)

        result = parse_single_email(email_content, colleagues, redactor)

        assert result is not None
        assert result["sender_name"] == "john_smith_developer"
        assert result["sender_email"] == "[EMAIL]"  # PII redacted
        assert result["sender_role"] == "Developer"
        assert result["body"] == "This is the email body content."
