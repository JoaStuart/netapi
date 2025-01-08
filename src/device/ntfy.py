import json
from typing import Any, Literal, Optional
import config
from webclient.client_request import WebClient, WebMethod


type _Priority = Literal[1, 2, 3, 4, 5]


class NtfyAdapter:
    def __init__(self) -> None:
        self._ip = config.load("ntfy.ip", str)
        self._port = config.load("ntfy.port", int)
        self._topic = config.load("ntfy.default_topic", str)

        self._title: Optional[str] = None
        self._message: Optional[tuple[str, bool]] = None
        self._tags: list[str] = []
        self._priority: _Priority = 3
        self._actions: list[dict[str, Any]] = []

        self._data: dict[str, Any] = {}

    def set_title(self, title: str) -> "NtfyAdapter":
        self._title = title
        return self

    def set_topic(self, topic: str) -> "NtfyAdapter":
        self._topic = topic
        return self

    def set_message(self, message: str, markdown: bool = True) -> "NtfyAdapter":
        self._message = message, markdown
        return self

    def set_tags(self, *tags: str) -> "NtfyAdapter":
        self._tags = list(tags)
        return self

    def set_priority(self, priority: _Priority) -> "NtfyAdapter":
        self._priority = priority
        return self

    def add_url_action(
        self,
        label: str,
        url: str,
        clear: bool = True,
    ) -> "NtfyAdapter":
        self._actions.append(
            {
                "action": "view",
                "label": label,
                "url": url,
                "clear": clear,
            }
        )
        return self

    def add_http_action(
        self,
        label: str,
        url: str,
        body: str,
        headers: dict[str, str] = {},
        clear: bool = True,
    ) -> "NtfyAdapter":
        self._actions.append(
            {
                "action": "http",
                "label": label,
                "url": url,
                "body": body,
                "headers": headers,
                "clear": clear,
            }
        )
        return self

    def read_json(self, data: dict[str, Any]) -> "NtfyAdapter":
        self._data = data
        return self

    def dispatch(self) -> None:
        body = {
            "topic": self._topic,
            "title": self._title,
            "tags": self._tags,
            "priority": self._priority,
            "actions": self._actions,
        }

        if self._message:
            body["message"] = self._message[0]
            body["markdown"] = self._message[1]

        body |= self._data

        req = (
            WebClient(self._ip, self._port)
            .set_secure(False)
            .set_method(WebMethod.POST)
            .set_json(body)
        )

        resp = req.send()
        if resp.code != 200:
            raise ValueError(
                f"Could not dispatch notification: {resp.code} {resp.msg} {resp.body}"
            )
