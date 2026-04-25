"""
MCP (Model Context Protocol) clients for groww-pulse project.

Provides Google Docs and Gmail API integration.
"""

from .gdocs_client import get_access_token, check_doc_exists, create_pulse_doc
from .gmail_client import create_draft, send_draft, get_draft_details, list_drafts

__all__ = [
    'get_access_token',
    'check_doc_exists', 
    'create_pulse_doc',
    'create_draft',
    'send_draft',
    'get_draft_details',
    'list_drafts'
]
