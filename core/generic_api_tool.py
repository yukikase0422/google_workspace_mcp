"""
Generic API Tool (Staged Tool Pattern)

This module provides a unified Google Workspace tool that uses a staged pattern:
1. gws(category="calendar") -> List available actions
2. gws(category="calendar", action="create_event") -> Show field descriptions
3. gws(category="calendar", action="create_event", fields={...}) -> Execute

This pattern conserves context by allowing incremental discovery of capabilities.
"""

import inspect
import logging
import re
import types
import typing
from importlib import import_module
from typing import Any, Callable, Dict, List, Optional, Tuple

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
                "handler": "gcalendar.calendar_tools.list_calendars",
            },
            "get_events": {
                "description": "Get events from a calendar (single or multiple)",
                "handler": "gcalendar.calendar_tools.get_events",
            },
            "manage_event": {
                "description": "Create, update, delete, or RSVP to calendar events",
                "handler": "gcalendar.calendar_tools.manage_event",
            },
            "manage_out_of_office": {
                "description": "Manage out-of-office calendar events",
                "handler": "gcalendar.calendar_tools.manage_out_of_office",
                "aliases": {"title": "summary"},
            },
            "manage_focus_time": {
                "description": "Manage focus time calendar events",
                "handler": "gcalendar.calendar_tools.manage_focus_time",
                "aliases": {"title": "summary"},
            },
            "query_freebusy": {
                "description": "Query free/busy information for calendars",
                "handler": "gcalendar.calendar_tools.query_freebusy",
                "aliases": {"calendars": "calendar_ids"},
            },
            "create_calendar": {
                "description": "Create a new calendar",
                "handler": "gcalendar.calendar_tools.create_calendar",
            },
        },
    },
    "gmail": {
        "description": "Gmail operations",
        "actions": {
            "search_gmail_messages": {
                "description": "Search Gmail messages",
                "handler": "gmail.gmail_tools.search_gmail_messages",
            },
            "get_gmail_message_content": {
                "description": "Get full content of a Gmail message",
                "handler": "gmail.gmail_tools.get_gmail_message_content",
            },
            "get_gmail_messages_content_batch": {
                "description": "Get content of multiple Gmail messages",
                "handler": "gmail.gmail_tools.get_gmail_messages_content_batch",
            },
            "get_gmail_attachment_content": {
                "description": "Download a Gmail attachment",
                "handler": "gmail.gmail_tools.get_gmail_attachment_content",
            },
            "send_gmail_message": {
                "description": "Send a Gmail message",
                "handler": "gmail.gmail_tools.send_gmail_message",
            },
            "draft_gmail_message": {
                "description": "Create a Gmail draft",
                "handler": "gmail.gmail_tools.draft_gmail_message",
            },
            "get_gmail_thread_content": {
                "description": "Get content of a Gmail thread",
                "handler": "gmail.gmail_tools.get_gmail_thread_content",
            },
            "get_gmail_threads_content_batch": {
                "description": "Get content of multiple Gmail threads",
                "handler": "gmail.gmail_tools.get_gmail_threads_content_batch",
            },
            "list_gmail_labels": {
                "description": "List all Gmail labels",
                "handler": "gmail.gmail_tools.list_gmail_labels",
            },
            "manage_gmail_label": {
                "description": "Create, update, or delete Gmail labels",
                "handler": "gmail.gmail_tools.manage_gmail_label",
            },
            "list_gmail_filters": {
                "description": "List all Gmail filters",
                "handler": "gmail.gmail_tools.list_gmail_filters",
            },
            "manage_gmail_filter": {
                "description": "Create or delete Gmail filters",
                "handler": "gmail.gmail_tools.manage_gmail_filter",
                "aliases": {"actions": "filter_action"},
            },
            "modify_gmail_message_labels": {
                "description": "Add or remove labels from a message",
                "handler": "gmail.gmail_tools.modify_gmail_message_labels",
                "aliases": {"add_labels": "add_label_ids", "remove_labels": "remove_label_ids"},
            },
            "batch_modify_gmail_message_labels": {
                "description": "Batch modify labels on multiple messages",
                "handler": "gmail.gmail_tools.batch_modify_gmail_message_labels",
                "aliases": {"add_labels": "add_label_ids", "remove_labels": "remove_label_ids"},
            },
        },
    },
    "drive": {
        "description": "Google Drive operations",
        "actions": {
            "search_drive_files": {
                "description": "Search files and folders in Drive",
                "handler": "gdrive.drive_tools.search_drive_files",
            },
            "get_drive_file_content": {
                "description": "Get content of a Drive file",
                "handler": "gdrive.drive_tools.get_drive_file_content",
            },
            "get_drive_file_download_url": {
                "description": "Get download URL for a Drive file",
                "handler": "gdrive.drive_tools.get_drive_file_download_url",
            },
            "list_drive_items": {
                "description": "List items in a Drive folder",
                "handler": "gdrive.drive_tools.list_drive_items",
            },
            "create_drive_folder": {
                "description": "Create a folder in Drive",
                "handler": "gdrive.drive_tools.create_drive_folder",
                "aliases": {"name": "folder_name", "parent_id": "parent_folder_id"},
            },
            "create_drive_file": {
                "description": "Create a file in Drive from text content or from a URL the server can fetch. To upload a file from your own environment, use create_drive_upload_session",
                "handler": "gdrive.drive_tools.create_drive_file",
                "aliases": {"name": "file_name", "parent_id": "folder_id", "content_url": "fileUrl", "file_url": "fileUrl"},
            },
            "create_drive_upload_session": {
                "description": "Start an upload of a file from your own environment (e.g. a PDF): returns a one-time URL to PUT the bytes to with curl, so the content never passes through tool arguments",
                "handler": "gdrive.drive_tools.create_drive_upload_session",
                "aliases": {"name": "file_name", "parent_id": "folder_id"},
            },
            "import_to_google_doc": {
                "description": "Import content to Google Docs format",
                "handler": "gdrive.drive_tools.import_to_google_doc",
                "aliases": {"name": "file_name", "parent_id": "folder_id", "source_url": "file_url"},
            },
            "get_drive_file_permissions": {
                "description": "Get permissions for a Drive file",
                "handler": "gdrive.drive_tools.get_drive_file_permissions",
            },
            "check_drive_file_public_access": {
                "description": "Check whether files with a given name are publicly accessible",
                "handler": "gdrive.drive_tools.check_drive_file_public_access",
            },
            "update_drive_file": {
                "description": "Update a Drive file's content or metadata",
                "handler": "gdrive.drive_tools.update_drive_file",
            },
            "get_drive_shareable_link": {
                "description": "Get shareable link for a Drive file",
                "handler": "gdrive.drive_tools.get_drive_shareable_link",
            },
            "manage_drive_access": {
                "description": "Manage sharing and permissions for Drive files",
                "handler": "gdrive.drive_tools.manage_drive_access",
                "aliases": {"email": "share_with"},
            },
            "copy_drive_file": {
                "description": "Copy a Drive file",
                "handler": "gdrive.drive_tools.copy_drive_file",
                "aliases": {"parent_id": "parent_folder_id"},
            },
            "set_drive_file_permissions": {
                "description": "Set link sharing and permissions for a Drive file",
                "handler": "gdrive.drive_tools.set_drive_file_permissions",
            },
        },
    },
    "docs": {
        "description": "Google Docs operations",
        "actions": {
            "search_docs": {
                "description": "Search Google Docs by name",
                "handler": "gdocs.docs_tools.search_docs",
                "hints": {"query": "Search query", "page_size": "Max results"},
            },
            "get_doc_content": {
                "description": "Get content of a Google Doc",
                "handler": "gdocs.docs_tools.get_doc_content",
            },
            "list_docs_in_folder": {
                "description": "List Google Docs in a folder",
                "handler": "gdocs.docs_tools.list_docs_in_folder",
                "hints": {"folder_id": "Folder ID", "page_size": "Max results"},
            },
            "create_doc": {
                "description": "Create a new Google Doc",
                "handler": "gdocs.docs_tools.create_doc",
            },
            "modify_doc_text": {
                "description": "Modify text in a Google Doc",
                "handler": "gdocs.docs_tools.modify_doc_text",
            },
            "find_and_replace_doc": {
                "description": "Find and replace text in a Google Doc",
                "handler": "gdocs.docs_tools.find_and_replace_doc",
            },
            "insert_doc_elements": {
                "description": "Insert elements (text, page breaks, tables) into a Doc",
                "handler": "gdocs.docs_tools.insert_doc_elements",
            },
            "insert_doc_image": {
                "description": "Insert an image into a Google Doc",
                "handler": "gdocs.docs_tools.insert_doc_image",
                "aliases": {"image_uri": "image_source"},
            },
            "update_doc_headers_footers": {
                "description": "Update headers and footers in a Doc",
                "handler": "gdocs.docs_tools.update_doc_headers_footers",
            },
            "batch_update_doc": {
                "description": "Batch update a Google Doc with multiple requests",
                "handler": "gdocs.docs_tools.batch_update_doc",
            },
            "inspect_doc_structure": {
                "description": "Inspect the structure of a Google Doc",
                "handler": "gdocs.docs_tools.inspect_doc_structure",
            },
            "create_table_with_data": {
                "description": "Create a table with data in a Google Doc",
                "handler": "gdocs.docs_tools.create_table_with_data",
                "aliases": {"data": "table_data"},
            },
            "debug_table_structure": {
                "description": "Debug table structure in a Google Doc",
                "handler": "gdocs.docs_tools.debug_table_structure",
            },
            "export_doc_to_pdf": {
                "description": "Export a Google Doc to PDF",
                "handler": "gdocs.docs_tools.export_doc_to_pdf",
                "aliases": {"destination_folder_id": "folder_id", "output_filename": "pdf_filename"},
            },
            "update_paragraph_style": {
                "description": "Update paragraph style in a Google Doc",
                "handler": "gdocs.docs_tools.update_paragraph_style",
            },
            "get_doc_as_markdown": {
                "description": "Get Google Doc content as Markdown",
                "handler": "gdocs.docs_tools.get_doc_as_markdown",
            },
            "insert_doc_tab": {
                "description": "Insert a new tab in a Google Doc",
                "handler": "gdocs.docs_tools.insert_doc_tab",
                "aliases": {"tab_title": "title"},
            },
            "delete_doc_tab": {
                "description": "Delete a tab from a Google Doc",
                "handler": "gdocs.docs_tools.delete_doc_tab",
            },
            "update_doc_tab": {
                "description": "Update a tab's properties in a Google Doc",
                "handler": "gdocs.docs_tools.update_doc_tab",
                "aliases": {"new_title": "title"},
            },
            "list_document_comments": {
                "description": "List all comments in a Google Doc",
                "handler": "gdocs.docs_tools.list_document_comments",
                "hints": {"document_id": "Document ID"},
            },
            "manage_document_comment": {
                "description": "Create, reply to, or resolve comments in a Doc",
                "handler": "gdocs.docs_tools.manage_document_comment",
                "hints": {"document_id": "Document ID", "action": "Action: create, reply, or resolve", "comment_content": "Comment text", "comment_id": "Comment ID (for reply/resolve)"},
            },
        },
    },
    "sheets": {
        "description": "Google Sheets operations",
        "actions": {
            "list_spreadsheets": {
                "description": "List spreadsheets from Drive",
                "handler": "gsheets.sheets_tools.list_spreadsheets",
            },
            "get_spreadsheet_info": {
                "description": "Get spreadsheet metadata and sheets list",
                "handler": "gsheets.sheets_tools.get_spreadsheet_info",
            },
            "read_sheet_values": {
                "description": "Read values from a sheet range",
                "handler": "gsheets.sheets_tools.read_sheet_values",
            },
            "modify_sheet_values": {
                "description": "Write or clear values in a sheet range",
                "handler": "gsheets.sheets_tools.modify_sheet_values",
            },
            "format_sheet_range": {
                "description": "Format cells in a sheet range",
                "handler": "gsheets.sheets_tools.format_sheet_range",
                "aliases": {"font_color": "text_color"},
            },
            "manage_conditional_formatting": {
                "description": "Manage conditional formatting rules",
                "handler": "gsheets.sheets_tools.manage_conditional_formatting",
            },
            "create_spreadsheet": {
                "description": "Create a new spreadsheet",
                "handler": "gsheets.sheets_tools.create_spreadsheet",
                "aliases": {"sheet_titles": "sheet_names"},
            },
            "create_sheet": {
                "description": "Add a new sheet to an existing spreadsheet",
                "handler": "gsheets.sheets_tools.create_sheet",
                "aliases": {"title": "sheet_name"},
            },
            "list_sheet_tables": {
                "description": "List tables (filter views) in a spreadsheet",
                "handler": "gsheets.sheets_tools.list_sheet_tables",
            },
            "append_table_rows": {
                "description": "Append rows to a sheet table",
                "handler": "gsheets.sheets_tools.append_table_rows",
            },
            "append_sheet_values": {
                "description": "Append values to a sheet",
                "handler": "gsheets.sheets_tools.append_sheet_values",
                "aliases": {"range_name": "range"},
            },
            "batch_read_sheet_values": {
                "description": "Read multiple ranges in one request",
                "handler": "gsheets.sheets_tools.batch_read_sheet_values",
            },
            "batch_modify_sheet_values": {
                "description": "Write to multiple ranges in one request",
                "handler": "gsheets.sheets_tools.batch_modify_sheet_values",
            },
            "batch_update_spreadsheet": {
                "description": "Batch update spreadsheet with multiple requests",
                "handler": "gsheets.sheets_tools.batch_update_spreadsheet",
            },
            "list_spreadsheet_comments": {
                "description": "List all comments in a spreadsheet",
                "handler": "gsheets.sheets_tools.list_spreadsheet_comments",
                "hints": {"spreadsheet_id": "Spreadsheet ID"},
            },
            "manage_spreadsheet_comment": {
                "description": "Create, reply to, or resolve comments",
                "handler": "gsheets.sheets_tools.manage_spreadsheet_comment",
                "hints": {"spreadsheet_id": "Spreadsheet ID", "action": "Action: create, reply, or resolve", "comment_content": "Comment text", "comment_id": "Comment ID (for reply/resolve)"},
            },
        },
    },
    "slides": {
        "description": "Google Slides operations",
        "actions": {
            "create_presentation": {
                "description": "Create a new presentation",
                "handler": "gslides.slides_tools.create_presentation",
            },
            "get_presentation": {
                "description": "Get presentation details",
                "handler": "gslides.slides_tools.get_presentation",
            },
            "batch_update_presentation": {
                "description": "Batch update a presentation",
                "handler": "gslides.slides_tools.batch_update_presentation",
            },
            "get_page": {
                "description": "Get details about a specific slide",
                "handler": "gslides.slides_tools.get_page",
            },
            "get_page_thumbnail": {
                "description": "Get thumbnail URL for a slide",
                "handler": "gslides.slides_tools.get_page_thumbnail",
            },
            "list_presentation_comments": {
                "description": "List all comments in a presentation",
                "handler": "gslides.slides_tools.list_presentation_comments",
                "hints": {"presentation_id": "Presentation ID"},
            },
            "manage_presentation_comment": {
                "description": "Create, reply to, or resolve comments",
                "handler": "gslides.slides_tools.manage_presentation_comment",
                "hints": {"presentation_id": "Presentation ID", "action": "Action: create, reply, or resolve", "comment_content": "Comment text", "comment_id": "Comment ID (for reply/resolve)"},
            },
        },
    },
    "forms": {
        "description": "Google Forms operations",
        "actions": {
            "create_form": {
                "description": "Create a new form",
                "handler": "gforms.forms_tools.create_form",
            },
            "get_form": {
                "description": "Get form details",
                "handler": "gforms.forms_tools.get_form",
            },
            "set_publish_settings": {
                "description": "Update form publish settings",
                "handler": "gforms.forms_tools.set_publish_settings",
            },
            "get_form_response": {
                "description": "Get a specific form response",
                "handler": "gforms.forms_tools.get_form_response",
            },
            "list_form_responses": {
                "description": "List form responses",
                "handler": "gforms.forms_tools.list_form_responses",
            },
            "batch_update_form": {
                "description": "Batch update a form",
                "handler": "gforms.forms_tools.batch_update_form",
            },
        },
    },
    "tasks": {
        "description": "Google Tasks operations",
        "actions": {
            "list_task_lists": {
                "description": "List all task lists",
                "handler": "gtasks.tasks_tools.list_task_lists",
            },
            "get_task_list": {
                "description": "Get details of a task list",
                "handler": "gtasks.tasks_tools.get_task_list",
            },
            "manage_task_list": {
                "description": "Create, update, delete, or clear task lists",
                "handler": "gtasks.tasks_tools.manage_task_list",
            },
            "list_tasks": {
                "description": "List tasks in a task list",
                "handler": "gtasks.tasks_tools.list_tasks",
            },
            "get_task": {
                "description": "Get details of a specific task",
                "handler": "gtasks.tasks_tools.get_task",
            },
            "manage_task": {
                "description": "Create, update, delete, or move tasks",
                "handler": "gtasks.tasks_tools.manage_task",
            },
        },
    },
    "chat": {
        "description": "Google Chat operations",
        "actions": {
            "list_spaces": {
                "description": "List Chat spaces (rooms and DMs)",
                "handler": "gchat.chat_tools.list_spaces",
                "hints": {"page_size": "Max results", "space_type": "Type: all, room, or dm"},
            },
            "get_messages": {
                "description": "Get messages from a Chat space",
                "handler": "gchat.chat_tools.get_messages",
                "hints": {"space_id": "Space ID", "page_size": "Max results", "order_by": "Sort order"},
            },
            "send_message": {
                "description": "Send a message to a Chat space",
                "handler": "gchat.chat_tools.send_message",
                "hints": {"space_id": "Space ID", "message_text": "Message text"},
            },
            "search_messages": {
                "description": "Search messages in Chat spaces",
                "handler": "gchat.chat_tools.search_messages",
            },
            "create_reaction": {
                "description": "Add an emoji reaction to a message",
                "handler": "gchat.chat_tools.create_reaction",
                "aliases": {"message_name": "message_id", "emoji": "emoji_unicode"},
            },
            "download_chat_attachment": {
                "description": "Download a Chat attachment",
                "handler": "gchat.chat_tools.download_chat_attachment",
            },
        },
    },
    "search": {
        "description": "Google Custom Search operations",
        "actions": {
            "search_custom": {
                "description": "Perform a custom search using Programmable Search Engine",
                "handler": "gsearch.search_tools.search_custom",
            },
            "get_search_engine_info": {
                "description": "Get Programmable Search Engine metadata",
                "handler": "gsearch.search_tools.get_search_engine_info",
            },
        },
    },
}


# -----------------------------------------------------------------------------
# Field introspection
#
# Field names, required-ness and defaults come from the handler's signature,
# and descriptions from its docstring "Args:" section, so that what gws shows
# and accepts can never drift from what the handler actually takes. Each action
# may also define:
#   aliases: legacy/alternative field names mapped to real parameter names
#   hints:   descriptions for parameters that the handler docstring omits
# -----------------------------------------------------------------------------

# Parameters injected by gws or by the service decorator, never set via fields.
_INJECTED_PARAMS = frozenset({"service", "user_google_email"})
_DOC_SECTION_HEADERS = frozenset({"Args:", "Arguments:", "Parameters:"})
_DOC_ARG_RE = re.compile(r"^(\s+)(\w+)\s*(?:\(([^)]*)\))?\s*:\s*(.*)$")
_MAX_TYPE_LABEL = 100


def _resolve_handler(action_info: Dict[str, Any]) -> Callable[..., Any]:
    """Import and return the handler function for an action."""
    module_path, func_name = action_info["handler"].rsplit(".", 1)
    module = import_module(module_path)
    handler = getattr(module, func_name)
    if not callable(handler):
        raise TypeError(f"Handler {action_info['handler']} is not callable")
    return handler


def _handler_params(handler: Callable[..., Any]) -> Dict[str, inspect.Parameter]:
    """Return the handler's settable parameters, in signature order."""
    params: Dict[str, inspect.Parameter] = {}
    for name, param in inspect.signature(handler).parameters.items():
        if name in _INJECTED_PARAMS:
            continue
        if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
            continue
        params[name] = param
    return params


def _docstring_args(handler: Callable[..., Any]) -> Dict[str, Tuple[Optional[str], str]]:
    """Parse a Google-style "Args:" section into {name: (type_label, description)}."""
    doc = inspect.getdoc(handler) or ""
    result: Dict[str, Tuple[Optional[str], str]] = {}
    in_args = False
    base_indent: Optional[int] = None
    current: Optional[str] = None
    for line in doc.splitlines():
        stripped = line.strip()
        if stripped in _DOC_SECTION_HEADERS:
            in_args, base_indent, current = True, None, None
            continue
        if not in_args:
            continue
        if stripped and not line[:1].isspace():
            # A new top-level section (e.g. "Returns:") ends the Args block.
            in_args, current = False, None
            continue
        if not stripped:
            continue
        indent = len(line) - len(line.lstrip())
        match = _DOC_ARG_RE.match(line)
        if match and (base_indent is None or indent <= base_indent):
            base_indent = indent if base_indent is None else base_indent
            current = match.group(2)
            result[current] = (match.group(3), match.group(4).strip())
        elif current is not None:
            type_label, text = result[current]
            result[current] = (type_label, f"{text} {stripped}".strip())
    return result


def _type_label(annotation: Any) -> str:
    """Render a type annotation compactly (Annotated/Optional unwrapped)."""
    if annotation is inspect.Parameter.empty:
        return "any"
    origin = typing.get_origin(annotation)
    args = typing.get_args(annotation)
    if origin is typing.Annotated:
        return _type_label(args[0])
    if origin is typing.Union or (
        hasattr(types, "UnionType") and isinstance(annotation, types.UnionType)
    ):
        members = [a for a in args if a is not type(None)]
        return " | ".join(_type_label(a) for a in members) or "None"
    if origin is typing.Literal:
        return "one of " + ", ".join(repr(a) for a in args)
    if origin is not None:
        name = getattr(origin, "__name__", str(origin))
        if args:
            return f"{name}[{', '.join(_type_label(a) for a in args)}]"
        return name
    if isinstance(annotation, type):
        return annotation.__name__
    return str(annotation).replace("typing.", "")


def _shorten(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _field_specs(action_info: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Describe each settable field of an action from its handler."""
    handler = _resolve_handler(action_info)
    doc_args = _docstring_args(handler)
    hints = action_info.get("hints", {})
    specs = []
    for name, param in _handler_params(handler).items():
        doc_type, doc_text = doc_args.get(name, (None, ""))
        specs.append(
            {
                "name": name,
                "type": _shorten(doc_type or _type_label(param.annotation), _MAX_TYPE_LABEL),
                "required": param.default is inspect.Parameter.empty,
                "default": None if param.default is inspect.Parameter.empty else param.default,
                "description": doc_text or hints.get(name, ""),
            }
        )
    return specs


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


def _format_field_line(spec: Dict[str, Any]) -> str:
    default = spec["default"]
    default_str = "" if spec["required"] or default is None else f" [default: {default!r}]"
    description = f": {spec['description']}" if spec["description"] else ""
    return f"  - {spec['name']} ({spec['type']}){default_str}{description}"


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

    try:
        specs = _field_specs(action_info)
    except Exception as e:  # noqa: BLE001 - report instead of failing discovery
        logger.error(f"Failed to inspect handler for {category}.{action}: {e}", exc_info=True)
        return f"{lines[0]}\nError: could not inspect the handler: {e}"

    required = [s for s in specs if s["required"]]
    optional = [s for s in specs if not s["required"]]

    for heading, group in (("Required fields:", required), ("\nOptional fields:", optional)):
        lines.append(heading)
        if group:
            lines.extend(_format_field_line(s) for s in group)
        else:
            lines.append("  (none)")

    aliases = action_info.get("aliases", {})
    if aliases:
        pairs = ", ".join(f"{old} -> {new}" for old, new in aliases.items())
        lines.append(f"\nAlso accepted: {pairs}")

    lines.append(f"\nUsage: gws(category=\"{category}\", action=\"{action}\", fields={{...}})")
    return "\n".join(lines)


def _map_fields(
    action_info: Dict[str, Any], params: Dict[str, inspect.Parameter], fields: Dict[str, Any]
) -> Tuple[Dict[str, Any], List[str]]:
    """Map caller fields onto handler parameters. Returns (kwargs, problems)."""
    aliases = action_info.get("aliases", {})
    mapped: Dict[str, Any] = {}
    sources: Dict[str, str] = {}
    problems: List[str] = []
    unknown: List[str] = []
    for key, value in fields.items():
        if key == "user_google_email":
            mapped[key] = value
            continue
        target = key if key in params else aliases.get(key)
        if target is None:
            unknown.append(key)
            continue
        if target in mapped:
            problems.append(f"'{key}' and '{sources[target]}' both set '{target}'")
            continue
        mapped[target] = value
        sources[target] = key
    if unknown:
        problems.insert(0, f"Unknown fields: {', '.join(unknown)}")
    missing = [
        name for name, param in params.items()
        if param.default is inspect.Parameter.empty and name not in mapped
    ]
    if missing:
        problems.append(f"Missing required fields: {', '.join(missing)}")
    return mapped, problems


async def _execute_action(category: str, action: str, fields: dict, user_google_email: str) -> str:
    """Execute the specified action with the given fields."""
    if category not in CATEGORIES:
        return f"Unknown category: {category}"

    cat_info = CATEGORIES[category]
    if action not in cat_info["actions"]:
        return f"Unknown action: {action} in category {category}"

    action_info = cat_info["actions"][action]
    handler_path = action_info["handler"]

    try:
        handler_func = _resolve_handler(action_info)
    except ImportError as e:
        logger.error(f"Failed to import handler {handler_path}: {e}")
        return f"Error: Failed to import handler for {category}.{action}: {e}"
    except (AttributeError, TypeError) as e:
        logger.error(f"Handler function not found {handler_path}: {e}")
        return f"Error: Handler function not found for {category}.{action}: {e}"

    mapped, problems = _map_fields(action_info, _handler_params(handler_func), fields)
    if problems:
        return "\n".join(problems) + f"\n\n{_format_field_info(category, action)}"

    try:
        call_args = {"user_google_email": user_google_email, **mapped}
        return await handler_func(**call_args)
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
