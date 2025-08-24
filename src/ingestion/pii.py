import re
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class PIIRedactor:
    """
    PII (Personally Identifiable Information) redaction utility.
    Redacts emails, phone numbers, IDs, and other sensitive information.
    """
    
    def __init__(self):
        # Email patterns
        self.email_pattern = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
        
        # Phone number patterns (Hungarian format)
        self.phone_pattern = re.compile(r'(\+36|06)?[\s-]?(\d{1,2})[\s-]?(\d{3})[\s-]?(\d{3,4})')
        
        # ID patterns (various formats)
        self.id_pattern = re.compile(r'\b\d{6}[A-Z]{2}\d{2}[A-Z]{2}\d{3}\b')  # Hungarian ID
        self.credit_card_pattern = re.compile(r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b')
        
        # IP address patterns
        self.ip_pattern = re.compile(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b')
        
        # URL patterns (but keep domain names for context)
        self.url_pattern = re.compile(r'https?://[^\s]+')
        
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
        redacted = self.email_pattern.sub('[EMAIL]', redacted)
        
        # Redact phone numbers
        redacted = self.phone_pattern.sub('[PHONE]', redacted)
        
        # Redact IDs
        redacted = self.id_pattern.sub('[ID]', redacted)
        redacted = self.credit_card_pattern.sub('[CARD]', redacted)
        
        # Redact IP addresses
        redacted = self.ip_pattern.sub('[IP]', redacted)
        
        # Redact URLs (but keep domain context)
        redacted = self.url_pattern.sub('[URL]', redacted)
        
        return redacted
    
    def redact_email_data(self, email_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Redact PII from email data structure.
        
        Args:
            email_data: Email data dictionary
            
        Returns:
            Redacted email data
        """
        redacted = email_data.copy()
        
        # Redact sender email
        if 'sender_email' in redacted:
            redacted['sender_email'] = '[EMAIL]'
        
        # Redact recipient emails
        if 'to_recipients' in redacted:
            for recipient in redacted['to_recipients']:
                if 'email' in recipient:
                    recipient['email'] = '[EMAIL]'
        
        if 'cc_recipients' in redacted:
            for recipient in redacted['cc_recipients']:
                if 'email' in recipient:
                    recipient['email'] = '[EMAIL]'
        
        # Redact body text
        if 'body' in redacted:
            redacted['body'] = self.redact_text(redacted['body'])
        
        return redacted
    
    def redact_thread_data(self, thread_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Redact PII from entire thread data.
        
        Args:
            thread_data: Thread data dictionary
            
        Returns:
            Redacted thread data
        """
        redacted = thread_data.copy()
        
        # Redact participants list
        if 'participants' in redacted:
            redacted['participants'] = ['[EMAIL]' for _ in redacted['participants']]
        
        # Redact individual emails
        if 'emails' in redacted:
            redacted['emails'] = [
                self.redact_email_data(email) for email in redacted['emails']
            ]
        
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

def redact_pii_from_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convenience function to redact PII from data structure.
    
    Args:
        data: Data dictionary (thread or email data)
        
    Returns:
        Redacted data
    """
    redactor = PIIRedactor()
    return redactor.redact_thread_data(data)