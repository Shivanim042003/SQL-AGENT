from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class LLMResponse:
    content: str
    model: str
    provider: str
    raw: Any | None = None


class LLMClient(ABC):

    @abstractmethod
    def complete(
        self,
        system: str,
        messages: list[dict],
        max_tokens: int = 1024
    ) -> LLMResponse:
        pass