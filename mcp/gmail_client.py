import os
import base64
import httpx
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, Any
from .gdocs_client import get_access_token


def create_draft(email_payload: Dict[str, Any]) -> str:
    """Create a Gmail draft with the provided email payload."""
    recipients = os.getenv("RECIPIENT_LIST", "")
    if not recipients:
        raise ValueError("No recipients configured. Please set RECIPIENT_LIST environment variable")
    
    recipient_list = [addr.strip() for addr in recipients.split(",") if addr.strip()]
    if not recipient_list:
        raise ValueError("No valid recipients found in RECIPIENT_LIST")
    
    # Check domain restrictions
    allowed_domain = os.getenv("ALLOWED_DOMAIN", "")
    external_ok = os.getenv("ENABLE_EXTERNAL_SEND", "false").lower() == "true"
    
    if not external_ok and allowed_domain:
        for addr in recipient_list:
            if allowed_domain not in addr.strip():
                raise ValueError(
                    f"Recipient {addr} not in allowed domain {allowed_domain}. "
                    "Set ENABLE_EXTERNAL_SEND=true to override."
                )
    
    try:
        token = get_access_token()
    except Exception as e:
        raise ValueError(f"Failed to get Gmail access token: {e}")
    
    # Create the email message
    msg = MIMEMultipart("alternative")
    msg["Subject"] = email_payload.get("subject", "Groww App Pulse Report")
    msg["To"] = ", ".join(recipient_list)
    msg["From"] = "me"
    
    # Add text and HTML parts
    body_text = email_payload.get("body_text", "")
    body_html = email_payload.get("body_html", "")
    
    if body_text:
        msg.attach(MIMEText(body_text, "plain"))
    
    if body_html:
        msg.attach(MIMEText(body_html, "html"))
    
    # Encode the message
    raw_message = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    
    try:
        # Create the draft
        resp = httpx.post(
            "https://gmail.googleapis.com/gmail/v1/users/me/drafts",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            json={
                "message": {
                    "raw": raw_message
                }
            }
        )
        resp.raise_for_status()
        
        draft_id = resp.json().get("id", "")
        print(f"Created Gmail draft with ID: {draft_id}")
        return draft_id
        
    except httpx.HTTPStatusError as e:
        print(f"HTTP error creating Gmail draft: {e.response.status_code} - {e.response.text}")
        raise
    except Exception as e:
        print(f"Error creating Gmail draft: {e}")
        raise


def send_draft(draft_id: str) -> bool:
    """Send a Gmail draft. Returns True if sent successfully."""
    if not draft_id:
        print("No draft ID provided")
        return False
    
    auto_send = os.getenv("AUTO_SEND", "false").lower() == "true"
    if not auto_send:
        print("AUTO_SEND is false — draft preserved, not sent")
        return False
    
    try:
        token = get_access_token()
    except Exception as e:
        print(f"Failed to get Gmail access token for sending: {e}")
        return False
    
    try:
        resp = httpx.post(
            "https://gmail.googleapis.com/gmail/v1/users/me/drafts/send",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            json={
                "id": draft_id
            }
        )
        
        if resp.status_code == 200:
            print(f"Successfully sent Gmail draft {draft_id}")
            return True
        else:
            print(f"Failed to send Gmail draft: {resp.status_code} - {resp.text}")
            return False
            
    except Exception as e:
        print(f"Error sending Gmail draft: {e}")
        return False


def get_draft_details(draft_id: str) -> Dict[str, Any]:
    """Get details of a Gmail draft."""
    if not draft_id:
        return {}
    
    try:
        token = get_access_token()
    except Exception as e:
        print(f"Failed to get Gmail access token: {e}")
        return {}
    
    try:
        resp = httpx.get(
            f"https://gmail.googleapis.com/gmail/v1/users/me/drafts/{draft_id}",
            headers={
                "Authorization": f"Bearer {token}"
            },
            params={
                "format": "metadata",
                "metadataHeaders": ["Subject", "To", "Date"]
            }
        )
        resp.raise_for_status()
        return resp.json()
        
    except Exception as e:
        print(f"Error getting draft details: {e}")
        return {}


def list_drafts(max_results: int = 10) -> list:
    """List recent Gmail drafts."""
    try:
        token = get_access_token()
    except Exception as e:
        print(f"Failed to get Gmail access token: {e}")
        return []
    
    try:
        resp = httpx.get(
            "https://gmail.googleapis.com/gmail/v1/users/me/drafts",
            headers={
                "Authorization": f"Bearer {token}"
            },
            params={
                "maxResults": max_results
            }
        )
        resp.raise_for_status()
        return resp.json().get("drafts", [])
        
    except Exception as e:
        print(f"Error listing drafts: {e}")
        return []


def test_gmail_client():
    """Test function to verify Gmail client works."""
    try:
        # Test token retrieval
        token = get_access_token()
        print("Successfully retrieved Gmail access token")
        
        # Test draft listing
        drafts = list_drafts(5)
        print(f"Found {len(drafts)} recent drafts")
        
        # Test email creation (will fail if recipients not configured)
        test_payload = {
            "subject": "Test Email from Groww Pulse",
            "body_text": "This is a test email.",
            "body_html": "<p>This is a <strong>test</strong> email.</p>"
        }
        
        try:
            draft_id = create_draft(test_payload)
            print(f"Created test draft: {draft_id}")
        except ValueError as e:
            print(f"Expected error (no recipients configured): {e}")
            
    except Exception as e:
        print(f"Gmail client test failed: {e}")
        print("This is expected if Google credentials are not configured")


if __name__ == "__main__":
    test_gmail_client()
