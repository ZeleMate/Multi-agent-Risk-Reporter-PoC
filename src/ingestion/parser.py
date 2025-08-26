import re
import os
import logging
import json
import hashlib
from typing import List, Dict, Any, Optional
import argparse
import dotenv
from datetime import datetime
from email.utils import parsedate_to_datetime
try:
    from src.ingestion.pii import PIIRedactor
    from src.ingestion.chunker import create_chunks
except ImportError:
    from src.ingestion.pii import PIIRedactor
    from src.ingestion.chunker import create_chunks

logger = logging.getLogger(__name__)

# Configure logging
logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

dotenv.load_dotenv()

input_dir = os.getenv("INPUT_DIR", "data/raw")
output_dir = os.getenv("OUTPUT_DIR", "data/clean")

def normalize_date(date_str: str) -> Dict[str, Any]:
    """
    Normalize date string to ISO8601 and epoch timestamp.

    Args:
        date_str: Raw date string from email

    Returns:
        Dict with normalized_date and epoch_timestamp
    """
    try:
        # Try to parse email date format
        dt = parsedate_to_datetime(date_str)
        iso_date = dt.isoformat()
        epoch_timestamp = int(dt.timestamp())
        return {
            'normalized_date': iso_date,
            'epoch_timestamp': epoch_timestamp
        }
    except Exception:
        # Fallback for non-standard date formats
        try:
            # Try common date patterns
            patterns = [
                (r'(\d{4})\.(\d{2})\.(\d{2}) (\d{2}):(\d{2})', '%Y.%m.%d %H:%M'),
                (r'(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})', '%Y-%m-%d %H:%M:%S'),
                (r'(\d{4})/(\d{2})/(\d{2}) (\d{2}):(\d{2})', '%Y/%m/%d %H:%M'),
            ]

            for pattern, fmt in patterns:
                match = re.search(pattern, date_str)
                if match:
                    dt = datetime.strptime(match.group(0), fmt)
                    iso_date = dt.isoformat()
                    epoch_timestamp = int(dt.timestamp())
                    return {
                        'normalized_date': iso_date,
                        'epoch_timestamp': epoch_timestamp
                    }
        except Exception:
            pass

        # If all parsing fails, return original with null epoch
        return {
            'normalized_date': date_str,
            'epoch_timestamp': None
        }

def parse_colleagues(colleagues_path: str) -> Dict[str, Dict[str, str]]:
    """
    Parse the colleagues.txt file and return a dictionary mapping email addresses to roles and names.
    """
    colleagues = {}
    try:
        with open(colleagues_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()
        
        for line in lines:
            line = line.strip()
            if line.startswith('Characters:') or not line:
                continue
            
            # Parse lines like: "Project Manager (PM): Péter Kovács (kovacs.peter@kisjozsitech.hu)"
            match = re.match(r'(.+?):\s*(.+?)\s*\((.+?)\)', line)
            if match:
                role = match.group(1).strip()
                name = match.group(2).strip()
                email = match.group(3).strip()
                
                colleagues[email] = {
                    'name': name,
                    'role': role,
                    'email': email
                }
        
        return colleagues
    
    except Exception as e:
        logger.error(f"Error parsing colleagues file {colleagues_path}: {e}")
        return {}

def parse_email_thread(email_path: str, colleagues: Dict[str, Dict[str, str]], redactor: PIIRedactor) -> Dict[str, Any]:
    """
    Parse an email thread file and return structured data.
    """
    try:
        with open(email_path, 'r', encoding='utf-8') as file:
            content = file.read()
        
        # Split content into individual emails using robust header detection
        # Find all "From:" at line beginnings
        email_matches = []
        lines = content.split('\n')
        current_email = []
        in_email = False

        for line in lines:
            # Check if this line starts a new email
            if line.startswith('From:'):
                # Save previous email if exists
                if current_email:
                    email_matches.append('\n'.join(current_email))
                    current_email = []

                # Start new email
                current_email = [line]
                in_email = True
            elif in_email:
                # Add line to current email
                current_email.append(line)

        # Add the last email if exists
        if current_email:
            email_matches.append('\n'.join(current_email))
        
        emails = []
        for i, email_content in enumerate(email_matches):
            email_content = email_content.strip()
            if not email_content:
                continue
                
            # Parse individual email
            email_data = parse_single_email(email_content, colleagues, redactor)
            if email_data:
                email_data['email_index'] = i
                emails.append(email_data)
        
        # Create thread summary with stable hash-based thread_id
        if emails:
            # Create stable thread identifier using hash of key components + file path to avoid collisions
            canonical_subject = emails[0].get('canonical_subject', '')
            participants = list(set([email['sender_email'] for email in emails]))
            participants_str = '_'.join(sorted(participants))

            file_abs_path = os.path.abspath(email_path)

            content_hash = hashlib.sha1(
                f"{canonical_subject}_{participants_str}_{len(emails)}_{file_abs_path}".encode('utf-8')
            ).hexdigest()[:12]

            thread_id = f"thread_{content_hash}"
        else:
            thread_id = os.path.basename(email_path).replace('.txt', '')
        
        thread_data = {
            'thread_id': thread_id,
            'file_path': email_path,
            'total_emails': len(emails),
            'participants': list(set([email['sender_email'] for email in emails])),
            'subject': emails[0]['subject'] if emails else '',
            'canonical_subject': emails[0].get('canonical_subject', '') if emails else '',
            'start_date': emails[0]['date'] if emails else '',
            'end_date': emails[-1]['date'] if emails else '',
            'emails': emails
        }
        
        return thread_data
    
    except Exception as e:
        logger.error(f"Error parsing email thread {email_path}: {e}")
        return {}

def _remove_quoted_replies(text: str) -> str:
    """
    Remove quoted replies from email body using simple heuristics.
    """
    if not text:
        return text

    lines = text.split('\n')
    clean_lines = []
    in_quote = False

    for line in lines:
        stripped = line.strip()

        # Detect quote markers
        quote_markers = [
            stripped.startswith('>'),  # Email quote
            stripped.startswith('|'),  # Some email clients
            stripped.startswith('On ') and 'wrote:' in stripped,  # "On [date] [person] wrote:"
            stripped.startswith('From:') and len(lines) > 1,  # Forwarded message header
            stripped.startswith('---') and 'Forwarded' in stripped,  # Forward marker
            stripped.startswith('Begin forwarded message:'),  # Forward marker
            re.match(r'^\d{4}[/-]\d{2}[/-]\d{2} \d{2}:\d{2}', stripped),  # Date at start
        ]

        if any(quote_markers):
            in_quote = True
            continue

        # If we were in a quote and encounter an empty line, stop quoting
        if in_quote and not stripped:
            in_quote = False
            continue

        # Skip lines that are part of quotes
        if in_quote:
            continue

        clean_lines.append(line)

    return '\n'.join(clean_lines).strip()

def parse_single_email(email_content: str, colleagues: Dict[str, Dict[str, str]], redactor: PIIRedactor) -> Optional[Dict[str, Any]]:
    """
    Parse a single email from the thread content.
    """
    try:
        # Extract From field - handle multiple formats and Unicode emails:
        # "Name email@domain.com", "Name <email@domain.com>", "Name (email@domain.com)"
        from_line = email_content.split('\n')[0]
        # Allow Unicode in local-part; keep ASCII domain/TLD
        email_re = r'[^<>\s()]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}'
        # Try angle brackets first
        from_match = re.search(rf'From:\s*(.+?)\s*<({email_re})>', from_line)
        if not from_match:
            # Try parentheses form
            from_match = re.search(rf'From:\s*(.+?)\s*\(({email_re})\)', from_line)
            if not from_match:
                # Try whitespace-separated name + email
                from_match = re.search(rf'From:\s*(.+?)\s+({email_re})', from_line)
                if not from_match:
                    logger.warning(f"Could not parse From line: {from_line}")
                    return None
        
        sender_info = from_match.group(1).strip()
        sender_email = from_match.group(2).strip()
        
        # Extract To field
        to_match = re.search(r'To:\s*(.+?)(?:\n|$)', email_content, re.MULTILINE)
        to_recipients = []
        if to_match:
            to_content = to_match.group(1).strip()
            to_recipients = parse_recipients(to_content)
        
        # Extract Cc field (optional)
        cc_match = re.search(r'Cc:\s*(.+?)(?:\n|$)', email_content, re.MULTILINE)
        cc_recipients = []
        if cc_match:
            cc_content = cc_match.group(1).strip()
            cc_recipients = parse_recipients(cc_content)
        
        # Extract Date field and normalize
        date_match = re.search(r'Date:\s*(.+?)(?:\n|$)', email_content, re.MULTILINE)
        date_str = date_match.group(1).strip() if date_match else ''
        date_normalized = normalize_date(date_str) if date_str else {'normalized_date': '', 'epoch_timestamp': None}
        
        # Extract Subject field
        subject_match = re.search(r'Subject:\s*(.+?)(?:\n|$)', email_content, re.MULTILINE)
        subject = subject_match.group(1).strip() if subject_match else ''
        
        # Extract body (everything after the headers)
        # Find the first empty line after headers
        lines = email_content.split('\n')
        body_start = 0
        for i, line in enumerate(lines):
            if line.strip() == '' and i > 0:
                body_start = i + 1
                break

        body_lines = lines[body_start:]
        body = '\n'.join(body_lines).strip()

        # Apply quoted reply detection and removal
        body = _remove_quoted_replies(body)
        
        # Get sender info from colleagues
        sender_role = colleagues.get(sender_email, {}).get('role', 'Unknown')
        sender_name = colleagues.get(sender_email, {}).get('name', sender_info.split()[0] if sender_info else 'Unknown')
        
        # Create canonical subject (strip RE:, FW:, etc.)
        canonical_subject = re.sub(r'^(RE:|FW:|FWD:)\s*', '', subject, flags=re.IGNORECASE).strip().lower()
        
        email_data = {
            'sender_name': sender_name,
            'sender_email': sender_email,
            'sender_role': sender_role,
            'to_recipients': to_recipients,
            'cc_recipients': cc_recipients,
            'date': date_str,
            'date_normalized': date_normalized['normalized_date'],
            'epoch_timestamp': date_normalized['epoch_timestamp'],
            'subject': subject,
            'canonical_subject': canonical_subject,
            'body': body,
            'body_length': len(body)
        }
        
        # Apply PII redaction
        return redactor.redact_email_data(email_data)
    
    except Exception as e:
        logger.error(f"Error parsing single email: {e}")
        return None

def parse_recipients(recipients_str: str) -> List[Dict[str, str]]:
    """
    Parse recipients string and return list of recipient dictionaries.
    """
    recipients = []
    if not recipients_str:
        return recipients
    
    # Split by comma and process each recipient
    for recipient in recipients_str.split(','):
        recipient = recipient.strip()
        if not recipient:
            continue
        
        # Try to extract email and name (allow Unicode in local-part)
        email_match = re.search(r'([^<>\s()]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})', recipient)
        if email_match:
            email = email_match.group(1)
            # Remove email from recipient string to get name
            name = recipient.replace(email, '').strip()
            if name.startswith('<') and name.endswith('>'):
                name = name[1:-1].strip()
            
            recipients.append({
                'name': name if name else 'Unknown',
                'email': email
            })
    
    return recipients

def process_email_data(input_dir: str, output_dir: str) -> None:
    """
    Process all email threads and colleagues data, then save structured output.
    """
    try:
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Find the colleagues file
        colleagues_file = None
        for root, dirs, files in os.walk(input_dir):
            if 'Colleagues.txt' in files:
                colleagues_file = os.path.join(root, 'Colleagues.txt')
                break
        
        if not colleagues_file:
            logger.error("Colleagues.txt not found in input directory")
            return
        
        # Parse colleagues
        colleagues = parse_colleagues(colleagues_file)

        # Initialize PII redactor
        redactor = PIIRedactor()

        # Create person_id mapping for consistent identification
        person_id_mapping = {}
        for email, data in colleagues.items():
            # Create stable person_id from name + role
            name_clean = data['name'].lower().replace(' ', '_')
            role_clean = data['role'].lower().replace(' ', '_').replace('(', '').replace(')', '')
            person_id = f"{name_clean}_{role_clean}"
            person_id_mapping[email] = person_id

        # Save colleagues data with person_id (PII protected)
        colleagues_clean = {}
        for email, data in colleagues.items():
            colleagues_clean[email] = {
                'person_id': person_id_mapping[email],
                'name': data['name'],
                'role': data['role'],
                'email_redacted': '[EMAIL]'  # Redacted for consistency
            }

        colleagues_output_path = os.path.join(output_dir, 'colleagues.json')
        with open(colleagues_output_path, 'w', encoding='utf-8') as f:
            json.dump(colleagues_clean, f, ensure_ascii=False, indent=2)
        
        # Find all email thread files
        email_files = []
        for root, dirs, files in os.walk(input_dir):
            for file in files:
                if file.startswith('email') and file.endswith('.txt'):
                    email_files.append(os.path.join(root, file))
        
        # Parse each email thread
        all_threads = []
        for email_file in sorted(email_files):
            thread_data = parse_email_thread(email_file, colleagues, redactor)
            if thread_data:
                all_threads.append(thread_data)
        
        # Save all threads data
        threads_output_path = os.path.join(output_dir, 'email_threads.json')
        with open(threads_output_path, 'w', encoding='utf-8') as f:
            json.dump(all_threads, f, ensure_ascii=False, indent=2)
        
        # Load chunking parameters from config if available
        chunk_size = 1000
        overlap = 100
        config_path = os.path.join(os.path.dirname(input_dir), 'configs', 'pipeline.yaml')
        if os.path.exists(config_path):
            try:
                import yaml
                with open(config_path, 'r') as f:
                    config = yaml.safe_load(f)
                chunk_size = config.get('chunking', {}).get('chunk_size', 1000)
                overlap = config.get('chunking', {}).get('overlap', 100)
            except Exception:
                logger.warning(f"Could not load config from {config_path}, using defaults")

        # Create chunks for vector store
        chunks = create_chunks(all_threads, chunk_size=chunk_size, overlap=overlap)
        chunks_output_path = os.path.join(output_dir, 'chunks.json')
        with open(chunks_output_path, 'w', encoding='utf-8') as f:
            json.dump(chunks, f, ensure_ascii=False, indent=2)
        
        # Create summary statistics
        summary = {
            'total_threads': len(all_threads),
            'total_emails': sum(thread['total_emails'] for thread in all_threads),
            'total_participants': len(colleagues),
            'date_processed': datetime.now().isoformat(),
            'threads': [{
                'thread_id': thread['thread_id'],
                'total_emails': thread['total_emails'],
                'subject': thread['subject'],
                'participants': thread['participants']
            } for thread in all_threads]
        }
        
        summary_output_path = os.path.join(output_dir, 'summary.json')
        with open(summary_output_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Successfully processed {len(all_threads)} email threads with {summary['total_emails']} total emails")
        logger.info(f"Output saved to {output_dir}")
        
    except Exception as e:
        logger.error(f"Error processing email data: {e}")
        raise

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parse email threads and colleagues data")
    parser.add_argument("--input-dir", type=str, default=input_dir, help="Input directory containing email files")
    parser.add_argument("--output-dir", type=str, default=output_dir, help="Output directory to save parsed data")
    args = parser.parse_args()
    
    process_email_data(args.input_dir, args.output_dir)