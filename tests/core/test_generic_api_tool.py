"""
Tests for the staged `gws` tool (core/generic_api_tool.py).

The central guarantee: the fields gws shows and accepts for every action are the
handler's real parameters, so a call built from the field listing always binds.
"""

import inspect
import os
import sys
from typing import Annotated, List, Optional
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from core import generic_api_tool as gat  # noqa: E402
from core.generic_api_tool import CATEGORIES  # noqa: E402


def _all_actions():
    for category, cat_info in CATEGORIES.items():
        for action, action_info in cat_info["actions"].items():
            yield category, action, action_info


ALL_ACTIONS = list(_all_actions())
ACTION_IDS = [f"{c}.{a}" for c, a, _ in ALL_ACTIONS]


@pytest.mark.parametrize("category,action,action_info", ALL_ACTIONS, ids=ACTION_IDS)
def test_handler_resolves_to_coroutine_function(category, action, action_info):
    handler = gat._resolve_handler(action_info)
    assert inspect.iscoroutinefunction(handler), f"{category}.{action} handler is not async"


@pytest.mark.parametrize("category,action,action_info", ALL_ACTIONS, ids=ACTION_IDS)
def test_aliases_and_hints_refer_to_real_parameters(category, action, action_info):
    params = gat._handler_params(gat._resolve_handler(action_info))
    for old, new in action_info.get("aliases", {}).items():
        assert old not in params, f"alias '{old}' shadows a real parameter"
        assert new in params, f"alias target '{new}' is not a parameter"
    for name in action_info.get("hints", {}):
        assert name in params, f"hint for unknown parameter '{name}'"
    assert set(action_info) <= {"description", "handler", "aliases", "hints"}


@pytest.mark.parametrize("category,action,action_info", ALL_ACTIONS, ids=ACTION_IDS)
def test_field_info_lists_every_parameter(category, action, action_info):
    text = gat._format_field_info(category, action)
    assert "Error" not in text.splitlines()[1]
    for name, param in gat._handler_params(gat._resolve_handler(action_info)).items():
        assert f"  - {name} (" in text, f"{name} missing from field info"
    required_block = text.split("Required fields:")[1].split("Optional fields:")[0]
    for spec in gat._field_specs(action_info):
        assert (f"  - {spec['name']} (" in required_block) == spec["required"]


@pytest.mark.parametrize("category,action,action_info", ALL_ACTIONS, ids=ACTION_IDS)
def test_required_fields_from_listing_bind_to_handler(category, action, action_info):
    handler = gat._resolve_handler(action_info)
    params = gat._handler_params(handler)
    fields = {name: "x" for name, p in params.items() if p.default is inspect.Parameter.empty}
    mapped, problems = gat._map_fields(action_info, params, fields)
    assert problems == []
    inspect.signature(handler).bind(user_google_email="u@example.com", **mapped)


def _create_drive_file_info():
    return CATEGORIES["drive"]["actions"]["create_drive_file"]


def test_create_drive_file_accepts_real_names():
    info = _create_drive_file_info()
    params = gat._handler_params(gat._resolve_handler(info))
    mapped, problems = gat._map_fields(
        info,
        params,
        {"file_name": "a.pdf", "folder_id": "F", "mime_type": "application/pdf", "fileUrl": "https://example.com/a.pdf"},
    )
    assert problems == []
    assert mapped == {"file_name": "a.pdf", "folder_id": "F", "mime_type": "application/pdf", "fileUrl": "https://example.com/a.pdf"}


def test_create_drive_file_maps_old_names():
    info = _create_drive_file_info()
    params = gat._handler_params(gat._resolve_handler(info))
    mapped, problems = gat._map_fields(
        info, params, {"name": "a.txt", "parent_id": "F", "content_url": "https://example.com/a.txt"}
    )
    assert problems == []
    assert mapped == {"file_name": "a.txt", "folder_id": "F", "fileUrl": "https://example.com/a.txt"}


def test_unknown_conflicting_and_missing_fields_are_reported():
    info = _create_drive_file_info()
    params = gat._handler_params(gat._resolve_handler(info))
    _, problems = gat._map_fields(info, params, {"convert_to": "doc"})
    assert problems[0] == "Unknown fields: convert_to"
    assert "Missing required fields: file_name" in problems
    _, problems = gat._map_fields(info, params, {"name": "a", "file_name": "b"})
    assert problems == ["'file_name' and 'name' both set 'file_name'"]


@pytest.mark.asyncio
async def test_execute_action_calls_handler_with_mapped_arguments():
    received = {}

    async def fake_handler(user_google_email: str, file_name: str, content: Optional[str] = None,
                           folder_id: str = "root", mime_type: str = "text/plain",
                           fileUrl: Optional[str] = None) -> str:
        received.update(locals())
        return "done"

    with patch.object(gat, "_resolve_handler", return_value=fake_handler):
        result = await gat._execute_action(
            "drive", "create_drive_file", {"name": "a.txt", "content": "hi"}, "u@example.com"
        )
    assert result == "done"
    assert received["file_name"] == "a.txt"
    assert received["content"] == "hi"
    assert received["user_google_email"] == "u@example.com"


@pytest.mark.asyncio
async def test_execute_action_rejects_unknown_fields_without_calling():
    called = False

    async def fake_handler(user_google_email: str, file_name: str) -> str:
        nonlocal called
        called = True
        return "done"

    with patch.object(gat, "_resolve_handler", return_value=fake_handler):
        result = await gat._execute_action(
            "drive", "create_drive_file", {"file_name": "a", "bogus": 1}, "u@example.com"
        )
    assert not called
    assert result.startswith("Unknown fields: bogus")
    assert "Action: drive.create_drive_file" in result


def test_docstring_args_parses_types_and_continuations():
    def sample(service, user_google_email: str, a: str, b: int = 1):
        """
        Does things.

        Args:
            a (str): First line
                continues here.
            b: Second
                - "x": choice

        Returns:
            str: ignored
        """

    parsed = gat._docstring_args(sample)
    assert parsed["a"] == ("str", "First line continues here.")
    assert parsed["b"] == (None, 'Second - "x": choice')
    assert "str" not in parsed


def test_type_label_unwraps_annotated_and_optional():
    assert gat._type_label(Optional[List[str]]) == "list[str]"
    assert gat._type_label(Annotated[int, "meta"]) == "int"
    assert gat._type_label(inspect.Parameter.empty) == "any"
