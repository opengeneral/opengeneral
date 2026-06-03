from __future__ import annotations

from io import StringIO

from opengeneral.runner import AgentChatRunner


class FakeResponder:
    def __init__(self) -> None:
        self.messages: list[tuple[str, str]] = []

    def send_message(self, name: str, content: str) -> dict[str, list[str]]:
        self.messages.append((name, content))
        if content == "/tools":
            return {"messages": ["No MCP tools are currently available."]}
        if not content:
            return {"messages": ["Give me a goal, or type '/tools' to inspect available tools."]}
        return {"messages": [f"I'm ready to work on that: {content}"]}


def test_chat_exits_on_slash_exit() -> None:
    output = StringIO()

    AgentChatRunner("tester", FakeResponder()).chat(StringIO("/exit\n"), output)

    assert "Talking to tester. Type /exit to leave." in output.getvalue()
    assert output.getvalue().endswith("tester> ")


def test_chat_shows_hint_on_empty_message() -> None:
    output = StringIO()

    AgentChatRunner("tester", FakeResponder()).chat(StringIO("\n/exit\n"), output)

    assert "Give me a goal, or type '/tools' to inspect available tools." in output.getvalue()


def test_chat_forwards_messages_to_responder() -> None:
    output = StringIO()
    responder = FakeResponder()

    AgentChatRunner("tester", responder).chat(StringIO("hello\n/exit\n"), output)

    assert responder.messages == [("tester", "hello")]
    assert "I'm ready to work on that: hello" in output.getvalue()


def test_chat_lists_no_tools_without_action_plane_clients() -> None:
    output = StringIO()

    AgentChatRunner("tester", FakeResponder()).chat(StringIO("/tools\n/exit\n"), output)

    assert "No MCP tools are currently available." in output.getvalue()
