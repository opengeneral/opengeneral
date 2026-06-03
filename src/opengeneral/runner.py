from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, TextIO

_EXIT_COMMANDS = {"/exit", "/quit"}


class ChatResponder(Protocol):
    def send_message(self, name: str, content: str) -> dict[str, list[str]]: ...


@dataclass(frozen=True)
class AgentChatRunner:
    agent_name: str
    responder: ChatResponder

    def chat(self, input_stream: TextIO, output_stream: TextIO) -> None:
        output_stream.write(f"Talking to {self.agent_name}. Type /exit to leave.\n\n")
        output_stream.flush()
        while True:
            output_stream.write(f"{self.agent_name}> ")
            output_stream.flush()
            message = input_stream.readline()
            if message == "":
                output_stream.write("\n")
                output_stream.flush()
                return
            request = message.strip()
            if request in _EXIT_COMMANDS:
                return
            result = self.responder.send_message(self.agent_name, request)
            for response in result.get("messages", []):
                output_stream.write(response)
                output_stream.write("\n")
            output_stream.write("\n")
            output_stream.flush()
