import json

from app.core.prompts import SYSTEM_PROMPT
from app.llm.ollama import OllamaClient
from app.models.schemas import (
    Command,
    LLMDecision,
    ResponseType
)


LLM_RESPONSE_PROMPT = """
You are Curly's decision and response generator.

Return ONLY valid JSON.

Supported commands:

NONE
FACE_AUTH
GET_TIME
GET_WEATHER
GET_LAB_INFO
END_CONVERSATION

Rules:

1. Use NONE for normal conversation.

2. Use FACE_AUTH only when the user is actually asking to
   authenticate, verify, scan, identify, or check themselves for access.

3. Use GET_TIME when the user asks for the current time.

4. Use GET_WEATHER when the user asks for current weather.

5. Use GET_LAB_INFO for institutional laboratory questions.

6. Use END_CONVERSATION when the user clearly wants to end the session.

7. Never decide whether a person is authorized.

8. Never invent current time or weather.

9. Use supplied knowledge when answering institutional questions.

10. Keep spoken responses short and natural.

11. If the user asks a normal conversational question, command must
    be NONE.

12. Confidence must be between 0 and 1.

Return exactly:

{
  "type": "response" or "command",
  "command": "NONE" or one of the supported commands,
  "text": "short spoken response",
  "confidence": 0.0
}
"""


class LLMResponseGenerator:

    def __init__(
        self,
        llm: OllamaClient
    ):
        self.llm = llm

    async def generate(
        self,
        user_text: str,
        history: list[dict[str, str]],
        knowledge_context: str = "",
        environment_context: dict | None = None
    ) -> LLMDecision:

        prompt = f"""
RELEVANT KNOWLEDGE:

{knowledge_context}

CURRENT ENVIRONMENT:

{environment_context or {}}

USER:

{user_text}
"""

        messages = [
            {
                "role": "system",
                "content": (
                    SYSTEM_PROMPT
                    + "\n"
                    + LLM_RESPONSE_PROMPT
                )
            }
        ]

        messages.extend(history)

        messages.append({
            "role": "user",
            "content": prompt
        })

        response = await self.llm.generate(
            messages=messages,
            response_format={
                "type": "object",
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": [
                            "response",
                            "command"
                        ]
                    },
                    "command": {
                        "type": "string",
                        "enum": [
                            "NONE",
                            "FACE_AUTH",
                            "GET_TIME",
                            "GET_WEATHER",
                            "GET_LAB_INFO",
                            "END_CONVERSATION"
                        ]
                    },
                    "text": {
                        "type": "string"
                    },
                    "confidence": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 1
                    }
                },
                "required": [
                    "type",
                    "command",
                    "text",
                    "confidence"
                ]
            }
        )

        try:

            data = json.loads(response)

            return LLMDecision(
                **data
            )

        except Exception:

            return LLMDecision(
                type=ResponseType.RESPONSE,
                command=Command.NONE,
                text=(
                    "I'm sorry, I didn't quite "
                    "understand that."
                ),
                confidence=0.0
            )