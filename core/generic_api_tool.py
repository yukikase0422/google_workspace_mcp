"""
Generic API Tool (Staged Tool Pattern)

This module provides a unified Google Workspace tool that uses a staged pattern:
1. gws(category="calendar") -> List available actions
2. gws(category="calendar", action="create_event") -> Show field descriptions
3. gws(category="calendar", action="create_event", fields={...}) -> Execute

This pattern conserves context by allowing incremental discovery of capabilities.
"""

import logging
from typing import Any, Dict, List, Optional

from core.server import server

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Category and Action Definitions
# -----------------------------------------------------------------------------

CATEGORIES: Dict[str, Dict[str, Any]] = {
    "calendar": {
        "description": "Google Calendar operations",
        "actions": {
            "list_calendars": {
                "description": "List all calendars accessible to the user",
                "required_fields": {},
                "optional_fields": {},
                "handler": "gcalendar.calendar_tools.list_calendars",
            },
            "get_events": {
                "description": "Get events from a calendar (single or multiple)",
                "required_fields": {},
                "optional_fields": {
                    "calendar_id": {"type": "str", "description": "Calendar ID (default: primary)", "default": "primary"},
                    "event_id": {"type": "str", "description": "Specific event ID to retrieve"},
                    "time_min": {"type": "str", "description": "Start time (RFC3339)"},
                    "time_max": {"type": "str", "description": "End time (RFC3339)"},
                    "max_results": {"type": "int", "description": "Maximum events to return", "default": 25},
                    "query": {"type": "str", "description": "Keyword search"},
                    "detailed": {"type": "bool", "description": "Include detailed info", "default": False},
                    "include_attachments": {"type": "bool", "description": "Include attachment info", "default": False},
                },
                "handler": "gcalendar.calendar_tools.get_events",
            },
            "manage_event": {
                "description": "Create, modify, delete, or RSVP to calendar events",
                "required_fields": {
                    "action": {"type": "str", "description": "Action: create, modify, delete, or rsvp"},
                },
                "optional_fields": {
                    "event_id": {"type": "str", "description": "Event ID (required for modify/delete/rsvp)"},
                    "calendar_id": {"type": "str", "description": "Calendar ID", "default": "primary"},
                    "summary": {"type": "str", "description": "Event title"},
                    "start_time": {"type": "str", "description": "Start time (RFC3339 or YYYY-MM-DD)"},
                    "end_time": {"type": "str", "description": "End time (RFC3339 or YYYY-MM-DD)"},
                    "description": {"type": "str", "description": "Event description"},
                    "location": {"type": "str", "description": "Event location"},
                    "attendees": {"type": "List[str]", "description": "List of attendee emails"},
                    "timezone": {"type": "str", "description": "IANA timezone"},
                    "add_google_meet": {"type": "bool", "description": "Add Google Meet link", "default": False},
                    "response": {"type": "str", "description": "RSVP response (accepted/declined/tentative)"},
                    "rsvp_comment": {"type": "str", "description": "RSVP comment"},
                    "send_updates": {"type": "str", "description": "Notification behavior"},
                },
                "handler": "gcalendar.calendar_tools.manage_event",
            },
            "manage_out_of_office": {
                "description": "Manage out-of-office calendar events",
                "required_fields": {
                    "action": {"type": "str", "description": "Action: create, list, update, or delete"},
                },
                "optional_fields": {
                    "event_id": {"type": "str", "description": "Event ID (for update/delete)"},
                    "calendar_id": {"type": "str", "description": "Calendar ID", "default": "primary"},
                    "title": {"type": "str", "description": "OOO title"},
                    "start_time": {"type": "str", "description": "Start time"},
                    "end_time": {"type": "str", "description": "End time"},
                    "auto_decline_mode": {"type": "str", "description": "Auto-decline mode"},
                    "decline_message": {"type": "str", "description": "Decline message"},
                },
                "handler": "gcalendar.calendar_tools.manage_out_of_office",
            },
            "manage_focus_time": {
                "description": "Manage focus time calendar events",
                "required_fields": {
                    "action": {"type": "str", "description": "Action: create, list, update, or delete"},
                },
                "optional_fields": {
                    "event_id": {"type": "str", "description": "Event ID (for update/delete)"},
                    "calendar_id": {"type": "str", "description": "Calendar ID", "default": "primary"},
                    "title": {"type": "str", "description": "Focus time title"},
                    "start_time": {"type": "str", "description": "Start time"},
                    "end_time": {"type": "str", "description": "End time"},
                    "chat_status": {"type": "str", "description": "Chat status during focus time"},
                    "auto_decline_mode": {"type": "str", "description": "Auto-decline mode"},
                    "decline_message": {"type": "str", "description": "Decline message"},
                },
                "handler": "gcalendar.calendar_tools.manage_focus_time",
            },
            "query_freebusy": {
                "description": "Query free/busy information for calendars",
                "required_fields": {
                    "time_min": {"type": "str", "description": "Start time (RFC3339)"},
                    "time_max": {"type": "str", "description": "End time (RFC3339)"},
                },
                "optional_fields": {
                    "calendars": {"type": "List[str]", "description": "Calendar IDs to query"},
                    "timezone": {"type": "str", "description": "Timezone for interpretation"},
                },
                "handler": "gcalendar.calendar_tools.query_freebusy",
            },
            "create_calendar": {
                "description": "Create a new calendar",
                "required_fields": {
                    "summary": {"type": "str", "description": "Calendar name"},
                },
                "optional_fields": {
                    "description": {"type": "str", "description": "Calendar description"},
                    "location": {"type": "str", "description": "Geographic location"},
                    "timezone": {"type": "str", "description": "IANA timezone"},
                },
                "handler": "gcalendar.calendar_tools.create_calendar",
            },
        },
    },
    "gmail": {
        "description": "Gmail operations",
        "actions": {
            "search_gmail_messages": {
                "description": "Search Gmail messages",
                "required_fields": {
                    "query": {"type": "str", "description": "Gmail search query"},
                },
                "optional_fields": {
                    "page_size": {"type": "int", "description": "Max results", "default": 10},
                    "page_token": {"type": "str", "description": "Pagination token"},
                },
                "handler": "gmail.gmail_tools.search_gmail_messages",
            },
            "get_gmail_message_content": {
                "description": "Get full content of a Gmail message",
                "required_fields": {
                    "message_id": {"type": "str", "description": "Message ID"},
                },
                "optional_fields": {
                    "body_format": {"type": "str", "description": "Format: text, html, or raw", "default": "text"},
                },
                "handler": "gmail.gmail_tools.get_gmail_message_content",
            },
            "get_gmail_messages_content_batch": {
                "description": "Get content of multiple Gmail messages",
                "required_fields": {
                    "message_ids": {"type": "List[str]", "description": "List of message IDs (max 25)"},
                },
                "optional_fields": {
                    "format": {"type": "str", "description": "full or metadata", "default": "full"},
                    "body_format": {"type": "str", "description": "Body format", "default": "text"},
                },
                "handler": "gmail.gmail_tools.get_gmail_messages_content_batch",
            },
            "get_gmail_attachment_content": {
                "description": "Download a Gmail attachment",
                "required_fields": {
                    "message_id": {"type": "str", "description": "Message ID"},
                    "attachment_id": {"type": "str", "description": "Attachment ID"},
                },
                "optional_fields": {},
                "handler": "gmail.gmail_tools.get_gmail_attachment_content",
            },
            "send_gmail_message": {
                "description": "Send a Gmail message",
                "required_fields": {
                    "to": {"type": "str", "description": "Recipient email(s)"},
                    "subject": {"type": "str", "description": "Email subject"},
                    "body": {"type": "str", "description": "Email body"},
                },
                "optional_fields": {
                    "cc": {"type": "str", "description": "CC recipients"},
                    "bcc": {"type": "str", "description": "BCC recipients"},
                    "reply_to_message_id": {"type": "str", "description": "Message ID to reply to"},
                    "attachment_paths": {"type": "List[str]", "description": "Local file paths to attach"},
                    "attachment_urls": {"type": "List[str]", "description": "URLs to attach"},
                },
                "handler": "gmail.gmail_tools.send_gmail_message",
            },
            "draft_gmail_message": {
                "description": "Create a Gmail draft",
                "required_fields": {
                    "to": {"type": "str", "description": "Recipient email(s)"},
                    "subject": {"type": "str", "description": "Email subject"},
                    "body": {"type": "str", "description": "Email body"},
                },
                "optional_fields": {
                    "cc": {"type": "str", "description": "CC recipients"},
                    "bcc": {"type": "str", "description": "BCC recipients"},
                    "reply_to_message_id": {"type": "str", "description": "Message ID to reply to"},
                    "attachment_paths": {"type": "List[str]", "description": "Local file paths to attach"},
                    "attachment_urls": {"type": "List[str]", "description": "URLs to attach"},
                },
                "handler": "gmail.gmail_tools.draft_gmail_message",
            },
            "get_gmail_thread_content": {
                "description": "Get content of a Gmail thread",
                "required_fields": {
                    "thread_id": {"type": "str", "description": "Thread ID"},
                },
                "optional_fields": {
                    "body_format": {"type": "str", "description": "Body format", "default": "text"},
                },
                "handler": "gmail.gmail_tools.get_gmail_thread_content",
            },
            "get_gmail_threads_content_batch": {
                "description": "Get content of multiple Gmail threads",
                "required_fields": {
                    "thread_ids": {"type": "List[str]", "description": "List of thread IDs"},
                },
                "optional_fields": {
                    "body_format": {"type": "str", "description": "Body format", "default": "text"},
                },
                "handler": "gmail.gmail_tools.get_gmail_threads_content_batch",
            },
            "list_gmail_labels": {
                "description": "List all Gmail labels",
                "required_fields": {},
                "optional_fields": {},
                "handler": "gmail.gmail_tools.list_gmail_labels",
            },
            "manage_gmail_label": {
                "description": "Create, update, or delete Gmail labels",
                "required_fields": {
                    "action": {"type": "str", "description": "Action: create, update, or delete"},
                },
                "optional_fields": {
                    "label_id": {"type": "str", "description": "Label ID (for update/delete)"},
                    "name": {"type": "str", "description": "Label name"},
                    "label_list_visibility": {"type": "str", "description": "Visibility in label list"},
                    "message_list_visibility": {"type": "str", "description": "Visibility in message list"},
                },
                "handler": "gmail.gmail_tools.manage_gmail_label",
            },
            "list_gmail_filters": {
                "description": "List all Gmail filters",
                "required_fields": {},
                "optional_fields": {},
                "handler": "gmail.gmail_tools.list_gmail_filters",
            },
            "manage_gmail_filter": {
                "description": "Create or delete Gmail filters",
                "required_fields": {
                    "action": {"type": "str", "description": "Action: create or delete"},
                },
                "optional_fields": {
                    "filter_id": {"type": "str", "description": "Filter ID (for delete)"},
                    "criteria": {"type": "dict", "description": "Filter criteria"},
                    "actions": {"type": "dict", "description": "Filter actions"},
                },
                "handler": "gmail.gmail_tools.manage_gmail_filter",
            },
            "modify_gmail_message_labels": {
                "description": "Add or remove labels from a message",
                "required_fields": {
                    "message_id": {"type": "str", "description": "Message ID"},
                },
                "optional_fields": {
                    "add_labels": {"type": "List[str]", "description": "Labels to add"},
                    "remove_labels": {"type": "List[str]", "description": "Labels to remove"},
                },
                "handler": "gmail.gmail_tools.modify_gmail_message_labels",
            },
            "batch_modify_gmail_message_labels": {
                "description": "Batch modify labels on multiple messages",
                "required_fields": {
                    "message_ids": {"type": "List[str]", "description": "List of message IDs"},
                },
                "optional_fields": {
                    "add_labels": {"type": "List[str]", "description": "Labels to add"},
                    "remove_labels": {"type": "List[str]", "description": "Labels to remove"},
                },
                "handler": "gmail.gmail_tools.batch_modify_gmail_message_labels",
            },
        },
    },
    "drive": {
        "description": "Google Drive operations",
        "actions": {
            "search_drive_files": {
                "description": "Search files and folders in Drive",
                "required_fields": {
                    "query": {"type": "str", "description": "Search query"},
                },
                "optional_fields": {
                    "page_size": {"type": "int", "description": "Max results", "default": 10},
                    "page_token": {"type": "str", "description": "Pagination token"},
                    "drive_id": {"type": "str", "description": "Shared drive ID"},
                    "include_items_from_all_drives": {"type": "bool", "description": "Include shared drive items", "default": True},
                    "corpora": {"type": "str", "description": "Bodies to query"},
                    "file_type": {"type": "str", "description": "File type filter"},
                    "detailed": {"type": "bool", "description": "Include detailed info", "default": True},
                },
                "handler": "gdrive.drive_tools.search_drive_files",
            },
            "get_drive_file_content": {
                "description": "Get content of a Drive file",
                "required_fields": {
                    "file_id": {"type": "str", "description": "File ID"},
                },
                "optional_fields": {},
                "handler": "gdrive.drive_tools.get_drive_file_content",
            },
            "get_drive_file_download_url": {
                "description": "Get download URL for a Drive file",
                "required_fields": {
                    "file_id": {"type": "str", "description": "File ID"},
                },
                "optional_fields": {},
                "handler": "gdrive.drive_tools.get_drive_file_download_url",
            },
            "list_drive_items": {
                "description": "List items in a Drive folder",
                "required_fields": {},
                "optional_fields": {
                    "folder_id": {"type": "str", "description": "Folder ID", "default": "root"},
                    "page_size": {"type": "int", "description": "Max results", "default": 50},
                    "page_token": {"type": "str", "description": "Pagination token"},
                    "order_by": {"type": "str", "description": "Sort order"},
                    "file_type": {"type": "str", "description": "File type filter"},
                    "detailed": {"type": "bool", "description": "Include detailed info", "default": True},
                },
                "handler": "gdrive.drive_tools.list_drive_items",
            },
            "create_drive_folder": {
                "description": "Create a folder in Drive",
                "required_fields": {
                    "name": {"type": "str", "description": "Folder name"},
                },
                "optional_fields": {
                    "parent_id": {"type": "str", "description": "Parent folder ID"},
                },
                "handler": "gdrive.drive_tools.create_drive_folder",
            },
            "create_drive_file": {
                "description": "Create a file in Drive",
                "required_fields": {
                    "name": {"type": "str", "description": "File name"},
                },
                "optional_fields": {
                    "content": {"type": "str", "description": "File content"},
                    "content_url": {"type": "str", "description": "URL to download content from"},
                    "mime_type": {"type": "str", "description": "MIME type"},
                    "parent_id": {"type": "str", "description": "Parent folder ID"},
                    "convert_to": {"type": "str", "description": "Convert to Google format"},
                },
                "handler": "gdrive.drive_tools.create_drive_file",
            },
            "import_to_google_doc": {
                "description": "Import content to Google Docs format",
                "required_fields": {
                    "name": {"type": "str", "description": "Document name"},
                },
                "optional_fields": {
                    "content": {"type": "str", "description": "Text/HTML/Markdown content"},
                    "source_url": {"type": "str", "description": "URL to import from"},
                    "parent_id": {"type": "str", "description": "Parent folder ID"},
                },
                "handler": "gdrive.drive_tools.import_to_google_doc",
            },
            "get_drive_file_permissions": {
                "description": "Get permissions for a Drive file",
                "required_fields": {
                    "file_id": {"type": "str", "description": "File ID"},
                },
                "optional_fields": {},
                "handler": "gdrive.drive_tools.get_drive_file_permissions",
            },
            "check_drive_file_public_access": {
                "description": "Check if a Drive file is publicly accessible",
                "required_fields": {
                    "file_id": {"type": "str", "description": "File ID"},
                },
                "optional_fields": {},
                "handler": "gdrive.drive_tools.check_drive_file_public_access",
            },
            "update_drive_file": {
                "description": "Update a Drive file's content or metadata",
                "required_fields": {
                    "file_id": {"type": "str", "description": "File ID"},
                },
                "optional_fields": {
                    "name": {"type": "str", "description": "New file name"},
                    "content": {"type": "str", "description": "New file content"},
                    "content_url": {"type": "str", "description": "URL to download content from"},
                    "mime_type": {"type": "str", "description": "New MIME type"},
                    "add_parents": {"type": "str", "description": "Parent IDs to add"},
                    "remove_parents": {"type": "str", "description": "Parent IDs to remove"},
                },
                "handler": "gdrive.drive_tools.update_drive_file",
            },
            "get_drive_shareable_link": {
                "description": "Get shareable link for a Drive file",
                "required_fields": {
                    "file_id": {"type": "str", "description": "File ID"},
                },
                "optional_fields": {},
                "handler": "gdrive.drive_tools.get_drive_shareable_link",
            },
            "manage_drive_access": {
                "description": "Manage sharing and permissions for Drive files",
                "required_fields": {
                    "file_id": {"type": "str", "description": "File ID"},
                    "action": {"type": "str", "description": "Action: grant, update, revoke, or list"},
                },
                "optional_fields": {
                    "email": {"type": "str", "description": "User/group email"},
                    "role": {"type": "str", "description": "Permission role"},
                    "share_type": {"type": "str", "description": "Share type: user, group, domain, or anyone"},
                    "permission_id": {"type": "str", "description": "Permission ID"},
                    "send_notification": {"type": "bool", "description": "Send notification email"},
                },
                "handler": "gdrive.drive_tools.manage_drive_access",
            },
            "copy_drive_file": {
                "description": "Copy a Drive file",
                "required_fields": {
                    "file_id": {"type": "str", "description": "Source file ID"},
                },
                "optional_fields": {
                    "name": {"type": "str", "description": "New file name"},
                    "parent_id": {"type": "str", "description": "Destination folder ID"},
                },
                "handler": "gdrive.drive_tools.copy_drive_file",
            },
            "set_drive_file_permissions": {
                "description": "Set link sharing and permissions for a Drive file",
                "required_fields": {
                    "file_id": {"type": "str", "description": "File ID"},
                },
                "optional_fields": {
                    "link_sharing": {"type": "str", "description": "Link sharing: off, reader, commenter, writer"},
                    "writers_can_share": {"type": "bool", "description": "Whether editors can share"},
                    "copy_requires_writer_permission": {"type": "bool", "description": "Prevent copying/downloading"},
                },
                "handler": "gdrive.drive_tools.set_drive_file_permissions",
            },
        },
    },
    "docs": {
        "description": "Google Docs operations",
        "actions": {
            "search_docs": {
                "description": "Search Google Docs by name",
                "required_fields": {
                    "query": {"type": "str", "description": "Search query"},
                },
                "optional_fields": {
                    "page_size": {"type": "int", "description": "Max results", "default": 10},
                },
                "handler": "gdocs.docs_tools.search_docs",
            },
            "get_doc_content": {
                "description": "Get content of a Google Doc",
                "required_fields": {
                    "document_id": {"type": "str", "description": "Document ID"},
                },
                "optional_fields": {
                    "suggestions_view_mode": {"type": "str", "description": "How to render suggestions", "default": "DEFAULT_FOR_CURRENT_ACCESS"},
                },
                "handler": "gdocs.docs_tools.get_doc_content",
            },
            "list_docs_in_folder": {
                "description": "List Google Docs in a folder",
                "required_fields": {},
                "optional_fields": {
                    "folder_id": {"type": "str", "description": "Folder ID", "default": "root"},
                    "page_size": {"type": "int", "description": "Max results", "default": 100},
                },
                "handler": "gdocs.docs_tools.list_docs_in_folder",
            },
            "create_doc": {
                "description": "Create a new Google Doc",
                "required_fields": {
                    "title": {"type": "str", "description": "Document title"},
                },
                "optional_fields": {
                    "content": {"type": "str", "description": "Initial content"},
                },
                "handler": "gdocs.docs_tools.create_doc",
            },
            "modify_doc_text": {
                "description": "Modify text in a Google Doc",
                "required_fields": {
                    "document_id": {"type": "str", "description": "Document ID"},
                    "start_index": {"type": "int", "description": "Start index"},
                },
                "optional_fields": {
                    "end_index": {"type": "int", "description": "End index"},
                    "text": {"type": "str", "description": "Text to insert"},
                    "tab_id": {"type": "str", "description": "Tab ID"},
                    "segment_id": {"type": "str", "description": "Segment ID"},
                    "end_of_segment": {"type": "bool", "description": "Insert at end of segment", "default": False},
                },
                "handler": "gdocs.docs_tools.modify_doc_text",
            },
            "find_and_replace_doc": {
                "description": "Find and replace text in a Google Doc",
                "required_fields": {
                    "document_id": {"type": "str", "description": "Document ID"},
                    "find_text": {"type": "str", "description": "Text to find"},
                    "replace_text": {"type": "str", "description": "Replacement text"},
                },
                "optional_fields": {
                    "match_case": {"type": "bool", "description": "Case sensitive", "default": False},
                },
                "handler": "gdocs.docs_tools.find_and_replace_doc",
            },
            "insert_doc_elements": {
                "description": "Insert elements (text, page breaks, tables) into a Doc",
                "required_fields": {
                    "document_id": {"type": "str", "description": "Document ID"},
                    "elements": {"type": "List[dict]", "description": "Elements to insert"},
                },
                "optional_fields": {},
                "handler": "gdocs.docs_tools.insert_doc_elements",
            },
            "insert_doc_image": {
                "description": "Insert an image into a Google Doc",
                "required_fields": {
                    "document_id": {"type": "str", "description": "Document ID"},
                    "image_uri": {"type": "str", "description": "Image URL or Drive file ID"},
                    "index": {"type": "int", "description": "Insert position"},
                },
                "optional_fields": {
                    "width": {"type": "float", "description": "Width in points"},
                    "height": {"type": "float", "description": "Height in points"},
                },
                "handler": "gdocs.docs_tools.insert_doc_image",
            },
            "update_doc_headers_footers": {
                "description": "Update headers and footers in a Doc",
                "required_fields": {
                    "document_id": {"type": "str", "description": "Document ID"},
                },
                "optional_fields": {
                    "header_text": {"type": "str", "description": "Header text"},
                    "footer_text": {"type": "str", "description": "Footer text"},
                },
                "handler": "gdocs.docs_tools.update_doc_headers_footers",
            },
            "batch_update_doc": {
                "description": "Batch update a Google Doc with multiple requests",
                "required_fields": {
                    "document_id": {"type": "str", "description": "Document ID"},
                    "requests": {"type": "List[dict]", "description": "List of update requests"},
                },
                "optional_fields": {},
                "handler": "gdocs.docs_tools.batch_update_doc",
            },
            "inspect_doc_structure": {
                "description": "Inspect the structure of a Google Doc",
                "required_fields": {
                    "document_id": {"type": "str", "description": "Document ID"},
                },
                "optional_fields": {
                    "start_index": {"type": "int", "description": "Start index"},
                    "end_index": {"type": "int", "description": "End index"},
                },
                "handler": "gdocs.docs_tools.inspect_doc_structure",
            },
            "create_table_with_data": {
                "description": "Create a table with data in a Google Doc",
                "required_fields": {
                    "document_id": {"type": "str", "description": "Document ID"},
                    "data": {"type": "List[List[str]]", "description": "Table data (2D array)"},
                },
                "optional_fields": {
                    "index": {"type": "int", "description": "Insert position"},
                    "end_of_segment": {"type": "bool", "description": "Insert at end", "default": True},
                },
                "handler": "gdocs.docs_tools.create_table_with_data",
            },
            "debug_table_structure": {
                "description": "Debug table structure in a Google Doc",
                "required_fields": {
                    "document_id": {"type": "str", "description": "Document ID"},
                    "table_index": {"type": "int", "description": "Table index (0-based)"},
                },
                "optional_fields": {},
                "handler": "gdocs.docs_tools.debug_table_structure",
            },
            "export_doc_to_pdf": {
                "description": "Export a Google Doc to PDF",
                "required_fields": {
                    "document_id": {"type": "str", "description": "Document ID"},
                },
                "optional_fields": {
                    "destination_folder_id": {"type": "str", "description": "Destination folder ID"},
                    "output_filename": {"type": "str", "description": "Output file name"},
                },
                "handler": "gdocs.docs_tools.export_doc_to_pdf",
            },
            "update_paragraph_style": {
                "description": "Update paragraph style in a Google Doc",
                "required_fields": {
                    "document_id": {"type": "str", "description": "Document ID"},
                },
                "optional_fields": {
                    "start_index": {"type": "int", "description": "Start index"},
                    "end_index": {"type": "int", "description": "End index"},
                    "heading_level": {"type": "str", "description": "Heading level (HEADING_1, etc.)"},
                    "alignment": {"type": "str", "description": "Text alignment"},
                },
                "handler": "gdocs.docs_tools.update_paragraph_style",
            },
            "get_doc_as_markdown": {
                "description": "Get Google Doc content as Markdown",
                "required_fields": {
                    "document_id": {"type": "str", "description": "Document ID"},
                },
                "optional_fields": {
                    "include_comments": {"type": "bool", "description": "Include comments", "default": False},
                },
                "handler": "gdocs.docs_tools.get_doc_as_markdown",
            },
            "insert_doc_tab": {
                "description": "Insert a new tab in a Google Doc",
                "required_fields": {
                    "document_id": {"type": "str", "description": "Document ID"},
                    "tab_title": {"type": "str", "description": "Tab title"},
                },
                "optional_fields": {},
                "handler": "gdocs.docs_tools.insert_doc_tab",
            },
            "delete_doc_tab": {
                "description": "Delete a tab from a Google Doc",
                "required_fields": {
                    "document_id": {"type": "str", "description": "Document ID"},
                    "tab_id": {"type": "str", "description": "Tab ID to delete"},
                },
                "optional_fields": {},
                "handler": "gdocs.docs_tools.delete_doc_tab",
            },
            "update_doc_tab": {
                "description": "Update a tab's properties in a Google Doc",
                "required_fields": {
                    "document_id": {"type": "str", "description": "Document ID"},
                    "tab_id": {"type": "str", "description": "Tab ID to update"},
                },
                "optional_fields": {
                    "new_title": {"type": "str", "description": "New tab title"},
                },
                "handler": "gdocs.docs_tools.update_doc_tab",
            },
            "list_document_comments": {
                "description": "List all comments in a Google Doc",
                "required_fields": {
                    "document_id": {"type": "str", "description": "Document ID"},
                },
                "optional_fields": {},
                "handler": "gdocs.docs_tools.list_document_comments",
            },
            "manage_document_comment": {
                "description": "Create, reply to, or resolve comments in a Doc",
                "required_fields": {
                    "document_id": {"type": "str", "description": "Document ID"},
                    "action": {"type": "str", "description": "Action: create, reply, or resolve"},
                },
                "optional_fields": {
                    "comment_content": {"type": "str", "description": "Comment text"},
                    "comment_id": {"type": "str", "description": "Comment ID (for reply/resolve)"},
                },
                "handler": "gdocs.docs_tools.manage_document_comment",
            },
        },
    },
    "sheets": {
        "description": "Google Sheets operations",
        "actions": {
            "list_spreadsheets": {
                "description": "List spreadsheets from Drive",
                "required_fields": {},
                "optional_fields": {
                    "max_results": {"type": "int", "description": "Max results", "default": 25},
                },
                "handler": "gsheets.sheets_tools.list_spreadsheets",
            },
            "get_spreadsheet_info": {
                "description": "Get spreadsheet metadata and sheets list",
                "required_fields": {
                    "spreadsheet_id": {"type": "str", "description": "Spreadsheet ID"},
                },
                "optional_fields": {},
                "handler": "gsheets.sheets_tools.get_spreadsheet_info",
            },
            "read_sheet_values": {
                "description": "Read values from a sheet range",
                "required_fields": {
                    "spreadsheet_id": {"type": "str", "description": "Spreadsheet ID"},
                },
                "optional_fields": {
                    "range_name": {"type": "str", "description": "Range (e.g., Sheet1!A1:D10)", "default": "A1:Z1000"},
                    "include_hyperlinks": {"type": "bool", "description": "Include hyperlinks", "default": False},
                    "include_notes": {"type": "bool", "description": "Include notes", "default": False},
                    "include_formulas": {"type": "bool", "description": "Include formulas", "default": False},
                },
                "handler": "gsheets.sheets_tools.read_sheet_values",
            },
            "modify_sheet_values": {
                "description": "Write or clear values in a sheet range",
                "required_fields": {
                    "spreadsheet_id": {"type": "str", "description": "Spreadsheet ID"},
                    "range_name": {"type": "str", "description": "Range to modify"},
                },
                "optional_fields": {
                    "values": {"type": "List[List[str]]", "description": "2D array of values"},
                    "value_input_option": {"type": "str", "description": "RAW or USER_ENTERED", "default": "USER_ENTERED"},
                    "clear_values": {"type": "bool", "description": "Clear the range", "default": False},
                },
                "handler": "gsheets.sheets_tools.modify_sheet_values",
            },
            "format_sheet_range": {
                "description": "Format cells in a sheet range",
                "required_fields": {
                    "spreadsheet_id": {"type": "str", "description": "Spreadsheet ID"},
                    "range_name": {"type": "str", "description": "Range to format"},
                },
                "optional_fields": {
                    "bold": {"type": "bool", "description": "Bold text"},
                    "italic": {"type": "bool", "description": "Italic text"},
                    "font_size": {"type": "int", "description": "Font size"},
                    "font_color": {"type": "str", "description": "Font color (hex)"},
                    "background_color": {"type": "str", "description": "Background color (hex)"},
                    "horizontal_alignment": {"type": "str", "description": "Alignment"},
                },
                "handler": "gsheets.sheets_tools.format_sheet_range",
            },
            "manage_conditional_formatting": {
                "description": "Manage conditional formatting rules",
                "required_fields": {
                    "spreadsheet_id": {"type": "str", "description": "Spreadsheet ID"},
                    "action": {"type": "str", "description": "Action: create, delete, or list"},
                },
                "optional_fields": {
                    "sheet_name": {"type": "str", "description": "Sheet name"},
                    "range_name": {"type": "str", "description": "Range for rule"},
                    "rule_index": {"type": "int", "description": "Rule index (for delete)"},
                    "condition_type": {"type": "str", "description": "Condition type"},
                    "condition_values": {"type": "List[str]", "description": "Condition values"},
                    "format_options": {"type": "dict", "description": "Format options"},
                },
                "handler": "gsheets.sheets_tools.manage_conditional_formatting",
            },
            "create_spreadsheet": {
                "description": "Create a new spreadsheet",
                "required_fields": {
                    "title": {"type": "str", "description": "Spreadsheet title"},
                },
                "optional_fields": {
                    "sheet_titles": {"type": "List[str]", "description": "Initial sheet names"},
                },
                "handler": "gsheets.sheets_tools.create_spreadsheet",
            },
            "create_sheet": {
                "description": "Add a new sheet to an existing spreadsheet",
                "required_fields": {
                    "spreadsheet_id": {"type": "str", "description": "Spreadsheet ID"},
                    "title": {"type": "str", "description": "Sheet title"},
                },
                "optional_fields": {},
                "handler": "gsheets.sheets_tools.create_sheet",
            },
            "list_sheet_tables": {
                "description": "List tables (filter views) in a spreadsheet",
                "required_fields": {
                    "spreadsheet_id": {"type": "str", "description": "Spreadsheet ID"},
                },
                "optional_fields": {},
                "handler": "gsheets.sheets_tools.list_sheet_tables",
            },
            "append_table_rows": {
                "description": "Append rows to a sheet table",
                "required_fields": {
                    "spreadsheet_id": {"type": "str", "description": "Spreadsheet ID"},
                    "range_name": {"type": "str", "description": "Table range"},
                    "values": {"type": "List[List[str]]", "description": "Rows to append"},
                },
                "optional_fields": {},
                "handler": "gsheets.sheets_tools.append_table_rows",
            },
            "append_sheet_values": {
                "description": "Append values to a sheet",
                "required_fields": {
                    "spreadsheet_id": {"type": "str", "description": "Spreadsheet ID"},
                    "range_name": {"type": "str", "description": "Range to append to"},
                    "values": {"type": "List[List[str]]", "description": "Values to append"},
                },
                "optional_fields": {
                    "value_input_option": {"type": "str", "description": "RAW or USER_ENTERED", "default": "USER_ENTERED"},
                },
                "handler": "gsheets.sheets_tools.append_sheet_values",
            },
            "batch_read_sheet_values": {
                "description": "Read multiple ranges in one request",
                "required_fields": {
                    "spreadsheet_id": {"type": "str", "description": "Spreadsheet ID"},
                    "ranges": {"type": "List[str]", "description": "List of ranges"},
                },
                "optional_fields": {},
                "handler": "gsheets.sheets_tools.batch_read_sheet_values",
            },
            "batch_modify_sheet_values": {
                "description": "Write to multiple ranges in one request",
                "required_fields": {
                    "spreadsheet_id": {"type": "str", "description": "Spreadsheet ID"},
                    "data": {"type": "List[dict]", "description": "List of {range, values} objects"},
                },
                "optional_fields": {
                    "value_input_option": {"type": "str", "description": "RAW or USER_ENTERED", "default": "USER_ENTERED"},
                },
                "handler": "gsheets.sheets_tools.batch_modify_sheet_values",
            },
            "batch_update_spreadsheet": {
                "description": "Batch update spreadsheet with multiple requests",
                "required_fields": {
                    "spreadsheet_id": {"type": "str", "description": "Spreadsheet ID"},
                    "requests": {"type": "List[dict]", "description": "List of update requests"},
                },
                "optional_fields": {},
                "handler": "gsheets.sheets_tools.batch_update_spreadsheet",
            },
            "list_spreadsheet_comments": {
                "description": "List all comments in a spreadsheet",
                "required_fields": {
                    "spreadsheet_id": {"type": "str", "description": "Spreadsheet ID"},
                },
                "optional_fields": {},
                "handler": "gsheets.sheets_tools.list_spreadsheet_comments",
            },
            "manage_spreadsheet_comment": {
                "description": "Create, reply to, or resolve comments",
                "required_fields": {
                    "spreadsheet_id": {"type": "str", "description": "Spreadsheet ID"},
                    "action": {"type": "str", "description": "Action: create, reply, or resolve"},
                },
                "optional_fields": {
                    "comment_content": {"type": "str", "description": "Comment text"},
                    "comment_id": {"type": "str", "description": "Comment ID (for reply/resolve)"},
                },
                "handler": "gsheets.sheets_tools.manage_spreadsheet_comment",
            },
        },
    },
    "slides": {
        "description": "Google Slides operations",
        "actions": {
            "create_presentation": {
                "description": "Create a new presentation",
                "required_fields": {},
                "optional_fields": {
                    "title": {"type": "str", "description": "Presentation title", "default": "Untitled Presentation"},
                },
                "handler": "gslides.slides_tools.create_presentation",
            },
            "get_presentation": {
                "description": "Get presentation details",
                "required_fields": {
                    "presentation_id": {"type": "str", "description": "Presentation ID"},
                },
                "optional_fields": {},
                "handler": "gslides.slides_tools.get_presentation",
            },
            "batch_update_presentation": {
                "description": "Batch update a presentation",
                "required_fields": {
                    "presentation_id": {"type": "str", "description": "Presentation ID"},
                    "requests": {"type": "List[dict]", "description": "List of update requests"},
                },
                "optional_fields": {},
                "handler": "gslides.slides_tools.batch_update_presentation",
            },
            "get_page": {
                "description": "Get details about a specific slide",
                "required_fields": {
                    "presentation_id": {"type": "str", "description": "Presentation ID"},
                    "page_object_id": {"type": "str", "description": "Page/slide ID"},
                },
                "optional_fields": {},
                "handler": "gslides.slides_tools.get_page",
            },
            "get_page_thumbnail": {
                "description": "Get thumbnail URL for a slide",
                "required_fields": {
                    "presentation_id": {"type": "str", "description": "Presentation ID"},
                    "page_object_id": {"type": "str", "description": "Page/slide ID"},
                },
                "optional_fields": {
                    "thumbnail_size": {"type": "str", "description": "Size: LARGE, MEDIUM, SMALL", "default": "MEDIUM"},
                },
                "handler": "gslides.slides_tools.get_page_thumbnail",
            },
            "list_presentation_comments": {
                "description": "List all comments in a presentation",
                "required_fields": {
                    "presentation_id": {"type": "str", "description": "Presentation ID"},
                },
                "optional_fields": {},
                "handler": "gslides.slides_tools.list_presentation_comments",
            },
            "manage_presentation_comment": {
                "description": "Create, reply to, or resolve comments",
                "required_fields": {
                    "presentation_id": {"type": "str", "description": "Presentation ID"},
                    "action": {"type": "str", "description": "Action: create, reply, or resolve"},
                },
                "optional_fields": {
                    "comment_content": {"type": "str", "description": "Comment text"},
                    "comment_id": {"type": "str", "description": "Comment ID (for reply/resolve)"},
                },
                "handler": "gslides.slides_tools.manage_presentation_comment",
            },
        },
    },
    "forms": {
        "description": "Google Forms operations",
        "actions": {
            "create_form": {
                "description": "Create a new form",
                "required_fields": {
                    "title": {"type": "str", "description": "Form title"},
                },
                "optional_fields": {
                    "description": {"type": "str", "description": "Form description"},
                    "document_title": {"type": "str", "description": "Document title"},
                },
                "handler": "gforms.forms_tools.create_form",
            },
            "get_form": {
                "description": "Get form details",
                "required_fields": {
                    "form_id": {"type": "str", "description": "Form ID"},
                },
                "optional_fields": {},
                "handler": "gforms.forms_tools.get_form",
            },
            "set_publish_settings": {
                "description": "Update form publish settings",
                "required_fields": {
                    "form_id": {"type": "str", "description": "Form ID"},
                },
                "optional_fields": {
                    "publish_as_template": {"type": "bool", "description": "Publish as template", "default": False},
                    "require_authentication": {"type": "bool", "description": "Require sign-in", "default": False},
                },
                "handler": "gforms.forms_tools.set_publish_settings",
            },
            "get_form_response": {
                "description": "Get a specific form response",
                "required_fields": {
                    "form_id": {"type": "str", "description": "Form ID"},
                    "response_id": {"type": "str", "description": "Response ID"},
                },
                "optional_fields": {},
                "handler": "gforms.forms_tools.get_form_response",
            },
            "list_form_responses": {
                "description": "List form responses",
                "required_fields": {
                    "form_id": {"type": "str", "description": "Form ID"},
                },
                "optional_fields": {
                    "page_size": {"type": "int", "description": "Max results", "default": 10},
                    "page_token": {"type": "str", "description": "Pagination token"},
                },
                "handler": "gforms.forms_tools.list_form_responses",
            },
            "batch_update_form": {
                "description": "Batch update a form",
                "required_fields": {
                    "form_id": {"type": "str", "description": "Form ID"},
                    "requests": {"type": "List[dict]", "description": "List of update requests"},
                },
                "optional_fields": {},
                "handler": "gforms.forms_tools.batch_update_form",
            },
        },
    },
    "tasks": {
        "description": "Google Tasks operations",
        "actions": {
            "list_task_lists": {
                "description": "List all task lists",
                "required_fields": {},
                "optional_fields": {
                    "max_results": {"type": "int", "description": "Max results", "default": 1000},
                    "page_token": {"type": "str", "description": "Pagination token"},
                },
                "handler": "gtasks.tasks_tools.list_task_lists",
            },
            "get_task_list": {
                "description": "Get details of a task list",
                "required_fields": {
                    "task_list_id": {"type": "str", "description": "Task list ID"},
                },
                "optional_fields": {},
                "handler": "gtasks.tasks_tools.get_task_list",
            },
            "manage_task_list": {
                "description": "Create, update, delete, or clear task lists",
                "required_fields": {
                    "action": {"type": "str", "description": "Action: create, update, delete, clear_completed"},
                },
                "optional_fields": {
                    "task_list_id": {"type": "str", "description": "Task list ID"},
                    "title": {"type": "str", "description": "Task list title"},
                },
                "handler": "gtasks.tasks_tools.manage_task_list",
            },
            "list_tasks": {
                "description": "List tasks in a task list",
                "required_fields": {
                    "task_list_id": {"type": "str", "description": "Task list ID"},
                },
                "optional_fields": {
                    "max_results": {"type": "int", "description": "Max results", "default": 20},
                    "page_token": {"type": "str", "description": "Pagination token"},
                    "show_completed": {"type": "bool", "description": "Show completed tasks", "default": True},
                    "show_deleted": {"type": "bool", "description": "Show deleted tasks", "default": False},
                    "show_hidden": {"type": "bool", "description": "Show hidden tasks", "default": False},
                    "due_max": {"type": "str", "description": "Upper bound for due date"},
                    "due_min": {"type": "str", "description": "Lower bound for due date"},
                },
                "handler": "gtasks.tasks_tools.list_tasks",
            },
            "get_task": {
                "description": "Get details of a specific task",
                "required_fields": {
                    "task_list_id": {"type": "str", "description": "Task list ID"},
                    "task_id": {"type": "str", "description": "Task ID"},
                },
                "optional_fields": {},
                "handler": "gtasks.tasks_tools.get_task",
            },
            "manage_task": {
                "description": "Create, update, delete, or move tasks",
                "required_fields": {
                    "task_list_id": {"type": "str", "description": "Task list ID"},
                    "action": {"type": "str", "description": "Action: create, update, delete, move"},
                },
                "optional_fields": {
                    "task_id": {"type": "str", "description": "Task ID"},
                    "title": {"type": "str", "description": "Task title"},
                    "notes": {"type": "str", "description": "Task notes"},
                    "due": {"type": "str", "description": "Due date (RFC3339)"},
                    "status": {"type": "str", "description": "Status: needsAction or completed"},
                    "parent": {"type": "str", "description": "Parent task ID"},
                    "previous": {"type": "str", "description": "Previous sibling task ID"},
                },
                "handler": "gtasks.tasks_tools.manage_task",
            },
        },
    },
    "chat": {
        "description": "Google Chat operations",
        "actions": {
            "list_spaces": {
                "description": "List Chat spaces (rooms and DMs)",
                "required_fields": {},
                "optional_fields": {
                    "page_size": {"type": "int", "description": "Max results", "default": 100},
                    "space_type": {"type": "str", "description": "Type: all, room, or dm", "default": "all"},
                },
                "handler": "gchat.chat_tools.list_spaces",
            },
            "get_messages": {
                "description": "Get messages from a Chat space",
                "required_fields": {
                    "space_id": {"type": "str", "description": "Space ID"},
                },
                "optional_fields": {
                    "page_size": {"type": "int", "description": "Max results", "default": 50},
                    "order_by": {"type": "str", "description": "Sort order", "default": "createTime desc"},
                    "message_filter": {"type": "str", "description": "Filter expression"},
                },
                "handler": "gchat.chat_tools.get_messages",
            },
            "send_message": {
                "description": "Send a message to a Chat space",
                "required_fields": {
                    "space_id": {"type": "str", "description": "Space ID"},
                    "message_text": {"type": "str", "description": "Message text"},
                },
                "optional_fields": {
                    "thread_key": {"type": "str", "description": "App-defined thread key"},
                    "thread_name": {"type": "str", "description": "Thread resource name"},
                },
                "handler": "gchat.chat_tools.send_message",
            },
            "search_messages": {
                "description": "Search messages in Chat spaces",
                "required_fields": {},
                "optional_fields": {
                    "query": {"type": "str", "description": "Search query"},
                    "space_id": {"type": "str", "description": "Restrict to specific space"},
                    "page_size": {"type": "int", "description": "Max results", "default": 25},
                    "time_filter": {"type": "str", "description": "Time filter expression"},
                    "max_spaces": {"type": "int", "description": "Max spaces to search", "default": 10},
                },
                "handler": "gchat.chat_tools.search_messages",
            },
            "create_reaction": {
                "description": "Add an emoji reaction to a message",
                "required_fields": {
                    "message_name": {"type": "str", "description": "Message resource name"},
                    "emoji": {"type": "str", "description": "Unicode emoji"},
                },
                "optional_fields": {},
                "handler": "gchat.chat_tools.create_reaction",
            },
            "download_chat_attachment": {
                "description": "Download a Chat attachment",
                "required_fields": {
                    "message_id": {"type": "str", "description": "Message ID"},
                    "attachment_index": {"type": "int", "description": "Attachment index"},
                },
                "optional_fields": {},
                "handler": "gchat.chat_tools.download_chat_attachment",
            },
        },
    },
    "search": {
        "description": "Google Custom Search operations",
        "actions": {
            "search_custom": {
                "description": "Perform a custom search using Programmable Search Engine",
                "required_fields": {
                    "q": {"type": "str", "description": "Search query"},
                },
                "optional_fields": {
                    "num": {"type": "int", "description": "Number of results (1-10)", "default": 10},
                    "start": {"type": "int", "description": "Start index", "default": 1},
                    "safe": {"type": "str", "description": "Safe search level", "default": "off"},
                    "search_type": {"type": "str", "description": "Search type (image)"},
                    "site_search": {"type": "str", "description": "Restrict to site"},
                    "date_restrict": {"type": "str", "description": "Date restriction"},
                    "file_type": {"type": "str", "description": "File type filter"},
                    "language": {"type": "str", "description": "Language code"},
                    "country": {"type": "str", "description": "Country code"},
                    "sites": {"type": "List[str]", "description": "List of sites to search"},
                },
                "handler": "gsearch.search_tools.search_custom",
            },
            "get_search_engine_info": {
                "description": "Get Programmable Search Engine metadata",
                "required_fields": {},
                "optional_fields": {},
                "handler": "gsearch.search_tools.get_search_engine_info",
            },
        },
    },
}


# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------

def _format_category_list() -> str:
    """Format the list of available categories."""
    lines = ["Available categories:\n"]
    for cat_name, cat_info in CATEGORIES.items():
        lines.append(f"  - {cat_name}: {cat_info['description']}")
    lines.append("\nUsage: gws(category=\"<name>\") to see available actions")
    return "\n".join(lines)


def _format_action_list(category: str) -> str:
    """Format the list of actions for a category."""
    if category not in CATEGORIES:
        return f"Unknown category: {category}\n\n{_format_category_list()}"

    cat_info = CATEGORIES[category]
    lines = [f"Category: {category} - {cat_info['description']}\n"]
    lines.append("Available actions:\n")

    for action_name, action_info in cat_info["actions"].items():
        lines.append(f"  - {action_name}: {action_info['description']}")

    lines.append(f"\nUsage: gws(category=\"{category}\", action=\"<name>\") to see required fields")
    return "\n".join(lines)


def _format_field_info(category: str, action: str) -> str:
    """Format the field information for an action."""
    if category not in CATEGORIES:
        return f"Unknown category: {category}"

    cat_info = CATEGORIES[category]
    if action not in cat_info["actions"]:
        return f"Unknown action: {action} in category {category}\n\n{_format_action_list(category)}"

    action_info = cat_info["actions"][action]
    lines = [f"Action: {category}.{action}"]
    lines.append(f"Description: {action_info['description']}\n")

    # Required fields
    lines.append("Required fields:")
    if action_info["required_fields"]:
        for field_name, field_info in action_info["required_fields"].items():
            lines.append(f"  - {field_name} ({field_info['type']}): {field_info['description']}")
    else:
        lines.append("  (none)")

    # Optional fields
    lines.append("\nOptional fields:")
    if action_info["optional_fields"]:
        for field_name, field_info in action_info["optional_fields"].items():
            default_str = f" [default: {field_info['default']}]" if "default" in field_info else ""
            lines.append(f"  - {field_name} ({field_info['type']}): {field_info['description']}{default_str}")
    else:
        lines.append("  (none)")

    lines.append(f"\nUsage: gws(category=\"{category}\", action=\"{action}\", fields={{...}})")
    return "\n".join(lines)


async def _execute_action(category: str, action: str, fields: dict, user_google_email: str) -> str:
    """Execute the specified action with the given fields."""
    if category not in CATEGORIES:
        return f"Unknown category: {category}"

    cat_info = CATEGORIES[category]
    if action not in cat_info["actions"]:
        return f"Unknown action: {action} in category {category}"

    action_info = cat_info["actions"][action]

    # Validate required fields
    missing_fields = []
    for field_name in action_info["required_fields"]:
        if field_name not in fields:
            missing_fields.append(field_name)

    if missing_fields:
        return f"Missing required fields: {', '.join(missing_fields)}\n\n{_format_field_info(category, action)}"

    # Import and call the handler
    handler_path = action_info["handler"]
    try:
        module_path, func_name = handler_path.rsplit(".", 1)
        from importlib import import_module
        module = import_module(module_path)
        handler_func = getattr(module, func_name)

        # Add user_google_email to fields
        call_args = {"user_google_email": user_google_email, **fields}

        # Call the handler
        result = await handler_func(**call_args)
        return result
    except ImportError as e:
        logger.error(f"Failed to import handler {handler_path}: {e}")
        return f"Error: Failed to import handler for {category}.{action}: {e}"
    except AttributeError as e:
        logger.error(f"Handler function not found {handler_path}: {e}")
        return f"Error: Handler function not found for {category}.{action}: {e}"
    except TypeError as e:
        logger.error(f"Invalid arguments for {handler_path}: {e}")
        return f"Error: Invalid arguments for {category}.{action}: {e}"
    except Exception as e:
        logger.error(f"Error executing {handler_path}: {e}", exc_info=True)
        return f"Error executing {category}.{action}: {e}"


# -----------------------------------------------------------------------------
# Main Tool Function
# -----------------------------------------------------------------------------

@server.tool()
async def gws(
    category: str,
    action: Optional[str] = None,
    show_fields: bool = False,
    fields: Optional[Dict[str, Any]] = None,
    user_google_email: str = "",
) -> str:
    """
    Google Workspace unified tool with staged discovery pattern.

    This tool conserves context by allowing incremental discovery of capabilities.

    Usage stages:
    1. gws(category="<name>") - List available actions for a category
    2. gws(category="<name>", action="<action>") - Show field descriptions for an action
    3. gws(category="<name>", action="<action>", fields={...}) - Execute the action

    Args:
        category: The service category (calendar, gmail, drive, docs, sheets, slides, forms, tasks, chat, search)
        action: The action to perform within the category
        show_fields: If True, show field descriptions even when fields are provided
        fields: Dictionary of field values for execution
        user_google_email: The user's Google email address (auto-injected in single-user mode)

    Returns:
        str: Category/action list, field descriptions, or execution result

    Examples:
        # Stage 1: Discover categories
        gws(category="calendar")  # Lists all calendar actions

        # Stage 2: Discover fields
        gws(category="calendar", action="get_events")  # Shows required/optional fields

        # Stage 3: Execute
        gws(category="calendar", action="get_events", fields={"time_min": "2024-01-01T00:00:00Z"})
    """
    logger.info(f"[gws] category={category}, action={action}, show_fields={show_fields}, fields={fields}")

    # Validate category
    if category not in CATEGORIES:
        return f"Unknown category: {category}\n\n{_format_category_list()}"

    # Stage 1: List actions if no action specified
    if action is None:
        return _format_action_list(category)

    # Stage 2: Show field info if no fields or show_fields is True
    if fields is None or show_fields:
        return _format_field_info(category, action)

    # Stage 3: Execute the action
    return await _execute_action(category, action, fields, user_google_email)
