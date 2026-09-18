"""Tests for platform adapters."""

from __future__ import annotations

import json

import httpx
import pytest

from app.adapters import (
    AdapterError,
    BaleAdapter,
    EitaaAdapter,
    RubikaAdapter,
    build_adapter,
)
from app.adapters.base import MessageType


def test_build_adapter_types() -> None:
    assert isinstance(build_adapter("bale", "t"), BaleAdapter)
    assert isinstance(build_adapter("eitaa", "t"), EitaaAdapter)
    assert isinstance(build_adapter("rubika", "t"), RubikaAdapter)


def test_build_adapter_unknown_platform() -> None:
    with pytest.raises(AdapterError):
        build_adapter("telegram", "t")


def test_build_adapter_missing_token() -> None:
    with pytest.raises(AdapterError):
        build_adapter("bale", "")


def test_eitaa_is_destination_only() -> None:
    assert EitaaAdapter("t").supports_source is False
    assert BaleAdapter("t").supports_source is True
    assert RubikaAdapter("t").supports_source is True


def test_bale_copy_support() -> None:
    assert BaleAdapter("t").supports_copy_message is True
    assert RubikaAdapter("t").supports_copy_message is False


@pytest.mark.parametrize(
    ("payload", "expected_type", "expected_file_id"),
    [
        ({"text": "hi"}, MessageType.TEXT, None),
        (
            {
                "photo": [
                    {"file_id": "small", "file_size": 1},
                    {"file_id": "large", "file_size": 99},
                ]
            },
            MessageType.PHOTO,
            "large",
        ),
        ({"video": {"file_id": "v1"}}, MessageType.VIDEO, "v1"),
        ({"voice": {"file_id": "vo1"}}, MessageType.VOICE, "vo1"),
        ({"document": {"file_id": "d1"}}, MessageType.DOCUMENT, "d1"),
        ({"sticker": {"file_id": "s1"}}, MessageType.STICKER, "s1"),
        ({"location": {"latitude": 1.0, "longitude": 2.0}}, MessageType.LOCATION, None),
    ],
)
def test_detect_type(payload, expected_type, expected_file_id) -> None:
    assert BaleAdapter._detect_type(payload) == (expected_type, expected_file_id)


def test_parse_update_text() -> None:
    adapter = BaleAdapter("t")
    update = {
        "update_id": 1,
        "message": {"message_id": 5, "chat": {"id": 10}, "from": {"id": 1}, "text": "hello"},
    }
    msgs = adapter.parse_update(update)
    assert len(msgs) == 1
    assert msgs[0].message_type == MessageType.TEXT
    assert msgs[0].chat_id == "10"
    assert msgs[0].message_id == "5"
    assert msgs[0].text == "hello"


def test_parse_update_forward_flag() -> None:
    adapter = BaleAdapter("t")
    update = {
        "update_id": 1,
        "message": {"message_id": 1, "chat": {"id": 1}, "forward_from_chat": {"id": 9}},
    }
    msgs = adapter.parse_update(update)
    assert msgs[0].is_forwarded is True


async def test_send_message_request() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["json"] = json.loads(request.content)
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 77}})

    adapter = BaleAdapter("TOKEN", client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    result = await adapter.send_message("123", "hello")
    assert result == "77"
    assert captured["url"] == "https://tapi.bale.ai/botTOKEN/sendMessage"
    assert captured["json"]["chat_id"] == "123"
    assert captured["json"]["text"] == "hello"


async def test_send_message_api_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": False, "description": "bad request"})

    adapter = BaleAdapter("TOKEN", client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    with pytest.raises(AdapterError):
        await adapter.send_message("123", "hi")
