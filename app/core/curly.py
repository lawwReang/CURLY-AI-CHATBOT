import uuid
import re
from datetime import datetime
from pathlib import Path
import time

from app.config import settings
from app.core.intent import detect_command
from app.core.llm_response import LLMResponseGenerator
from app.core.prompts import SYSTEM_PROMPT
from app.core.session import Session
from app.knowledge.info_repository import InfoRepository
from app.llm.ollama import OllamaClient
from app.models.schemas import (
    Command,
    CurlyResponse,
    CurlyState,
    IntentSource,
    ResponseType,
)


class Curly:
    def __init__(
        self,
        llm: OllamaClient,
        knowledge,
        info_repo: InfoRepository | None = None,
    ):
        self.llm = llm
        self.knowledge = knowledge

        self.info_repo = info_repo or InfoRepository(
            Path(__file__).resolve().parents[1]
            / "knowledge"
            / "info_repo.json"
        )

        self.response_generator = LLMResponseGenerator(llm)

        self.sessions: dict[str, Session] = {}


        @property
        def info_repo(self) -> InfoRepository:
            if self._info_repo is None:
                self._info_repo = InfoRepository(
                Path(__file__).resolve().parents[1]
                / "knowledge"
                / "info_repo.json"
                )

            return self._info_repo

    # -----------------------------------------
    # SESSION
    # -----------------------------------------

    def create_session(self) -> str:
        self.cleanup_expired_sessions()

        session_id = str(uuid.uuid4())

        self.sessions[session_id] = Session(
            session_id=session_id
        )

        return session_id

    def get_session(
        self,
        session_id: str,
    ) -> Session:
        session = self.sessions.get(session_id)

        if session is None:
            session = Session(
                session_id=session_id
            )
            self.sessions[session_id] = session
            return session

        if session.is_expired(
            settings.session_timeout_seconds
        ):
            del self.sessions[session_id]

            session = Session(
                session_id=session_id
            )

            self.sessions[session_id] = session

        return session

    def get_history(
        self,
        session_id: str,
    ):
        return self.get_session(session_id).history

    def save_message(
        self,
        session_id: str,
        role: str,
        content: str,
    ):
        history = self.get_history(session_id)

        history.append(
            {
                "role": role,
                "content": content,
            }
        )

        max_messages = settings.max_history * 2

        if len(history) > max_messages:
            del history[:-max_messages]

    def clear_session(
        self,
        session_id: str,
    ):
        self.sessions.pop(
            session_id,
            None,
        )

    def set_state(
        self,
        session_id: str,
        state: CurlyState,
    ):
        session = self.get_session(session_id)
        session.set_state(state)

    def get_state(
        self,
        session_id: str,
    ) -> CurlyState:
        session = self.get_session(session_id)
        return session.state

    def cleanup_expired_sessions(self):
        expired_ids = []

        for session_id, session in self.sessions.items():
            if session.is_expired(
                settings.session_timeout_seconds
            ):
                expired_ids.append(session_id)

        for session_id in expired_ids:
            del self.sessions[session_id]

    # -----------------------------------------
    # KNOWLEDGE TOPIC
    # -----------------------------------------

    def detect_knowledge_topic(
        self,
        text: str,
    ) -> str | None:
        text = text.lower().strip()

        organization_terms = [
            "icar",
            "nrcy",
            "nrc yak",
            "nrc on yak",
            "national research centre on yak",
            "national research center on yak",
            "yak research centre",
            "yak research center",
            "dirang yak centre",
            "dirang yak center",
            "director of nrcy",
            "who is the director",
            "what does nrcy do",
            "what is nrcy",
            "where is nrcy",
            "yak research",
            "yak breeding",
            "yak nutrition",
            "yak health",
            "yak fibre",
            "yak fiber",
            "yak products",
            "churpi",
            "ftai",
            "iot",
            "assam don bosco university",
            "centre of excellence",
            "center of excellence",
        ]

        lab_terms = [
            "lab",
            "laboratory",
            "in-charge",
            "in charge",
            "nodal officer",
            "lab in-charge",
            "lab incharge",
            "opening time",
            "closing time",
            "working hours",
            "lab timings",
        ]

        if any(
            term in text
            for term in organization_terms
        ):
            return "organization"

        if any(
            term in text
            for term in lab_terms
        ):
            return "lab"

        return None
    
       # -----------------------------------------
    # PERSON RESOLUTION
    # -----------------------------------------

    def resolve_person(
        self,
        text: str,
    ) -> dict | None:

        normalized = (
            text.lower()
            .strip()
            .replace("-", " ")
        )

        # Normalize punctuation.
        normalized = re.sub(
            r"[^a-z0-9\s]",
            " ",
            normalized,
        )

        normalized = " ".join(
            normalized.split()
        )

        # -------------------------------------
        # DR. RUPESH MANDAL
        # -------------------------------------

        rupesh_aliases = (
            "rupesh mandal",
            "dr rupesh mandal",
            "dr rupesh",
            "rupesh mandel",
        )

        if any(
            alias in normalized
            for alias in rupesh_aliases
        ):
            return {
                "name": "Dr. Rupesh Mandal",
                "designation": "Assistant Professor",
                "organization": "Assam Don Bosco University",
            }

        # -------------------------------------
        # DR. MIHIR SARKAR
        # -------------------------------------

        mihir_aliases = (
            "mihir sarkar",
            "dr mihir sarkar",
            "mihir sircar",
            "mihir sarker",
            "dr mehir sarkar",
            "mehir sarkar",
            "mehir sakhar",
            "mihir sakhar",
        )

        if any(
            alias in normalized
            for alias in mihir_aliases
        ):
            return {
                "name": "Dr. Mihir Sarkar",
                "designation": "Director",
                "organization": (
                    "ICAR–National Research Centre on Yak"
                ),
            }

        return None
    # -----------------------------------------
    # DETERMINISTIC COMMAND RESPONSE
    # -----------------------------------------

    def command_response(
        self,
        command: Command,
        source: IntentSource,
    ) -> CurlyResponse:

        # TIME
        if command == Command.GET_TIME:
            current_time = datetime.now().strftime(
                "%I:%M %p"
            )

            return CurlyResponse(
                type=ResponseType.RESPONSE,
                command=Command.GET_TIME,
                text=(
                    f"The current time is "
                    f"{current_time}."
                ),
                state=CurlyState.SPEAKING,
                intent_source=source,
            )
        
        # DATE
        if command == Command.GET_DATE:
            current_date = datetime.now().strftime(
                "%B %d, %Y"
            )

            return CurlyResponse(
                type=ResponseType.RESPONSE,
                command=Command.GET_DATE,
                text=(
                    f"Today's date is "
                    f"{current_date}."
                ),
                state=CurlyState.SPEAKING,
                intent_source=source,
            )

        # FACE AUTH
        if command == Command.FACE_AUTH:
            return CurlyResponse(
                type=ResponseType.COMMAND,
                command=Command.FACE_AUTH,
                text="Sure! I'll verify you.",
                state=CurlyState.AUTHENTICATING,
                intent_source=source,
            )

        # WEATHER
        if command == Command.GET_WEATHER:
            return CurlyResponse(
                type=ResponseType.COMMAND,
                command=Command.GET_WEATHER,
                text="Let me check the current weather.",
                state=CurlyState.SPEAKING,
                intent_source=source,
            )

        # LAB INFO
        if command == Command.GET_LAB_INFO:
            return CurlyResponse(
                type=ResponseType.COMMAND,
                command=Command.GET_LAB_INFO,
                text="Sure, let me check that.",
                state=CurlyState.SPEAKING,
                intent_source=source,
            )

        # END CONVERSATION
        if command == Command.END_CONVERSATION:
            return CurlyResponse(
                type=ResponseType.COMMAND,
                command=Command.END_CONVERSATION,
                text="Alright. See you later!",
                state=CurlyState.IDLE,
                intent_source=source,
            )

        # FALLBACK
        return CurlyResponse(
            type=ResponseType.COMMAND,
            command=command,
            text="Sure.",
            state=CurlyState.SPEAKING,
            intent_source=source,
        )

    # -----------------------------------------
    # LAB DIRECT RESPONSE
    # -----------------------------------------
    def _get_lab_field(
    self,
    field: str,
):
        getter = getattr(
        self.knowledge,
        "get_lab_field",
        None,
    )

        if callable(getter):
            return getter(field)

        data = getattr(
            self.knowledge,
            "data",
            None,
    )

        if isinstance(data, dict):

            lab = data.get(
            "lab",
            {},
        )

            if isinstance(lab, dict):
                return lab.get(field)

        return None

    def lab_response(
        self,
        text: str,
    ) -> str | None:
        text_lower = text.lower().strip()

        # NODAL OFFICER
        if (
            "nodal officer" in text_lower
            or "nodal-officer" in text_lower
        ):
            name = self._get_lab_field(
                "nodal_officer"
            )

            if name:
                return (
                    "The nodal officer of the lab "
                    f"is {name}."
                )


        # IN-CHARGE
        if (
            "in-charge" in text_lower
            or "in charge" in text_lower
            or "lab incharge" in text_lower
        ):
            name = self._get_lab_field(
                "in_charge"
            )

            if name:
                return (
                    "The in-charge of the lab "
                    f"is {name}."
                )

            

        # LAB HOURS
        if (
            "open" in text_lower
            or "opening" in text_lower
            or "close" in text_lower
            or "closing" in text_lower
            or "timing" in text_lower
            or "timings" in text_lower
            or "working hours" in text_lower
            or "working days" in text_lower
        ):
            opening = self._get_lab_field(
                "opening_time"
            )

            closing = self._get_lab_field(
                "closing_time"
            )

            days = self._get_lab_field(
                "working_days"
            )

            if opening and closing and days:
                return (
                    f"The lab is open from {opening} "
                    f"to {closing}, {days}."
                )

            

        # LOCATION
        if (
            "where" in text_lower
            or "location" in text_lower
        ):
            location = self._get_lab_field(
                "location"
            )

            if location:
                return (
                    f"The lab is located at "
                    f"{location}."
                )

            

        # EMAIL
        if "email" in text_lower:
            email = self._get_lab_field(
                "email"
            )

            if email:
                return (
                    f"The lab email address is "
                    f"{email}."
                )


        # CONTACT
        if (
            "contact" in text_lower
            or "phone" in text_lower
            or "contact details" in text_lower
        ):
            contact = self._get_lab_field(
                "contact"
            )

            if contact:
                return (
                    f"You can contact "
                    f"{contact}."
                )

            

        # Generic lab question:
        # let the LLM answer from lab context.
        return None

    # -----------------------------------------
    # MAIN CHAT
    # -----------------------------------------

    async def chat(
        self,
        session_id: str,
        text: str,
        context: dict | None = None,
    ) -> CurlyResponse:

        session = self.get_session(session_id)

        original_text = text.strip()

        if not original_text:
            self.set_state(
                session_id,
                CurlyState.SPEAKING,
            )

            return CurlyResponse(
                type=ResponseType.RESPONSE,
                command=Command.NONE,
                text="I didn't hear anything.",
                state=CurlyState.SPEAKING,
                intent_source=IntentSource.DETERMINISTIC,
            )
        
        text, alias_matches = self.info_repo.normalize(original_text)

        # -----------------------------------------
        # PERSON QUERY
        # -----------------------------------------

        person = self.resolve_person(text)

        if person:

            lower_text = text.lower()

            person_query = any(
                phrase in lower_text
                for phrase in (
                    "who is",
                    "who's",
                    "what does",
                    "what is",
                    "what's",
                    "designation",
                    "role",
                    "position",
                    "department",
                    "which department",
                    "where does",
                    "where do",
                )
            )

            if person_query:

                response_text = (
                    f'{person["name"]} is a '
                    f'{person["designation"]} at '
                    f'{person["organization"]}.'
                )

                self.save_message(
                    session_id,
                    "user",
                    text,
                )

                self.save_message(
                    session_id,
                    "assistant",
                    response_text,
                )

                self.set_state(
                    session_id,
                    CurlyState.SPEAKING,
                )

                return CurlyResponse(
                    type=ResponseType.RESPONSE,
                    command=Command.NONE,
                    text=response_text,
                    state=CurlyState.SPEAKING,
                    intent_source=(
                        IntentSource.DETERMINISTIC
                    ),
                )

        session.set_state(
            CurlyState.PROCESSING
        )

        # -------------------------------------
        # 1. DETERMINISTIC INTENT
        # -------------------------------------

        detected = detect_command(text)

        if detected:

            # ---------------------------------
            # LAB KNOWLEDGE
            # ---------------------------------

            if detected.command in {
                Command.GET_LAB_INFO,
                Command.GET_LAB_IN_CHARGE,
                Command.GET_LAB_NODAL_OFFICER,
                Command.GET_LAB_HOURS,
                Command.GET_LAB_LOCATION,
                Command.GET_LAB_CONTACT,
                Command.GET_LAB_EMAIL,
            }:

                direct_response = self.lab_response(
                    text
                )

                if direct_response is not None:

                    self.save_message(
                        session_id,
                        "user",
                        text,
                    )

                    self.save_message(
                        session_id,
                        "assistant",
                        direct_response,
                    )

                    self.set_state(
                        session_id,
                        CurlyState.SPEAKING,
                    )

                    return CurlyResponse(
                        type=ResponseType.RESPONSE,
                        command=Command.NONE,
                        text=direct_response,
                        state=CurlyState.SPEAKING,
                        intent_source=(
                            IntentSource.DETERMINISTIC
                        ),
                    )


                # Generic lab question:
                # use the institutional context
                # with one LLM response.
                knowledge_context = (
                    self.knowledge.get_context("lab")
                )

                user_prompt = f"""
RELEVANT INSTITUTIONAL INFORMATION:

{knowledge_context}

SPEECH NORMALIZATION HINTS:

{self.info_repo.format_matches(alias_matches) or "None"}

USER QUESTION:

{text}

Answer using only the supplied institutional information.

Speech normalization hints only explain possible STT terminology
variants. They are not institutional facts and must never be treated
as facts by themselves.

Never invent institutional facts.

If the normalized institutional information still does not answer
the question, say:

"I don't have that information yet."

Keep the answer concise and natural because it will be spoken aloud.
"""

                messages = [
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT,
                    }
                ]

                messages.extend(
                    self.get_history(session_id)
                )

                messages.append(
                    {
                        "role": "user",
                        "content": user_prompt,
                    }
                )

                response_text = (
                    await self.llm.generate(
                        messages
                    )
                ).strip()

                self.save_message(
                    session_id,
                    "user",
                    text,
                )

                self.save_message(
                    session_id,
                    "assistant",
                    response_text,
                )

                self.set_state(
                    session_id,
                    CurlyState.SPEAKING,
                )

                return CurlyResponse(
                    type=ResponseType.RESPONSE,
                    command=Command.NONE ,
                    text=response_text,
                    state=CurlyState.SPEAKING,
                    intent_source=(
                        IntentSource.DETERMINISTIC
                    ),
                )

            # ---------------------------------
            # NORMAL APPLICATION COMMAND
            # ---------------------------------

            result = self.command_response(
                detected.command,
                IntentSource.DETERMINISTIC,
            )

            self.save_message(
                session_id,
                "user",
                text,
            )

            self.save_message(
                session_id,
                "assistant",
                result.text,
            )

            self.set_state(
                session_id,
                result.state,
            )

            return result

        # -------------------------------------
        # 2. KNOWLEDGE CONTEXT
        # -------------------------------------

        if self.resolve_person(text):
            return "person"

        topic = self.detect_knowledge_topic(text)

        if topic:
            knowledge_context = (
                self.knowledge.get_context(topic)
            )
        else:
            knowledge_context = ""


        # -------------------------------------
        # 3. NORMAL CONVERSATION / CONTEXT
        # -------------------------------------

        user_prompt = f"""
RELEVANT KNOWLEDGE:

{knowledge_context}

SPEECH NORMALIZATION HINTS:

{self.info_repo.format_matches(alias_matches) or "None"}

CURRENT ENVIRONMENT:

{context or {}}

USER:

{text}

Answer naturally using the conversation history.

Speech normalization hints are only there to help interpret
speech-to-text terminology variants. They are not institutional facts.

Use previous conversation turns to resolve references such as
"they", "he", "she", "it", or "that".

Do not invent institutional facts.

If institutional information is required and is not present in the
supplied knowledge, say:

"I don't have that information yet."

Keep the response concise and suitable for speech.
"""

        messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            }
        ]

        messages.extend(
            self.get_history(session_id)
        )

        messages.append(
            {
                "role": "user",
                "content": user_prompt,
            }
        )

        response_text = (
            await self.llm.generate(
                messages
            )
        ).strip()

        # -------------------------------------
        # 4. NORMAL LLM RESPONSE
        # -------------------------------------

        self.save_message(
            session_id,
            "user",
            text,
        )

        self.save_message(
            session_id,
            "assistant",
            response_text,
        )

        self.set_state(
            session_id,
            CurlyState.SPEAKING,
        )

        return CurlyResponse(
            type=ResponseType.RESPONSE,
            command=Command.NONE,
            text=response_text,
            state=CurlyState.SPEAKING,
            intent_source=IntentSource.LLM,
        )

        # -------------------------------------
        # 5. NORMAL LLM RESPONSE
        # -------------------------------------

        self.save_message(
            session_id,
            "user",
            text,
        )

        self.save_message(
            session_id,
            "assistant",
            response_text,
        )

        self.set_state(
            session_id,
            CurlyState.SPEAKING,
        )

        return CurlyResponse(
            type=ResponseType.RESPONSE,
            command=Command.NONE,
            text=response_text,
            state=CurlyState.SPEAKING,
            intent_source=IntentSource.LLM,
        )
    
    async def stream_normal_response(
        self,
        session_id: str,
        text: str,
        context: dict | None = None,
    ):
        """
        Stream ordinary conversational responses.

        Deterministic commands and explicit lab responses are intentionally
        excluded; those continue through the normal chat() path.
        """

        session = self.get_session(session_id)

        original_text = text.strip()

        if not original_text:
            yield ""
            return

        normalized_text, alias_matches = (
            self.info_repo.normalize(original_text)
        )

        # -----------------------------------------
        # Do not stream commands.
        # Let normal chat() handle them.
        # -----------------------------------------

        detected = detect_command(
            normalized_text
        )

        if detected is not None:
            response = await self.chat(
                session_id=session_id,
                text=original_text,
                context=context,
            )

            yield response.text or ""
            return

        # -----------------------------------------
        # Do not stream deterministic lab answers.
        # -----------------------------------------

        direct_response = self.lab_response(
            normalized_text
        )

        if direct_response is not None:

            response = await self.chat(
                session_id=session_id,
                text=original_text,
                context=context,
            )

            yield response.text or ""
            return

        # -----------------------------------------
        # KNOWLEDGE CONTEXT
        # -----------------------------------------

        topic = self.detect_knowledge_topic(
            normalized_text
        )

        if topic:

            knowledge_context = (
                self.knowledge.get_context(
                    topic
                )
            )

        else:

            knowledge_context = ""

        normalization_hints = (
            self.info_repo.format_matches(
                alias_matches
            )
            or "None"
        )

        # -----------------------------------------
        # STREAMING PROMPT
        # -----------------------------------------

        user_prompt = f"""
    RELEVANT KNOWLEDGE:

    {knowledge_context}

    SPEECH NORMALIZATION HINTS:

    {normalization_hints}

    CURRENT ENVIRONMENT:

    {context or {}}

    USER:

    {normalized_text}

    Answer naturally using the conversation history.

    Speech normalization hints are only terminology interpretation.
    They are not institutional facts.

    Use previous conversation turns to resolve references such as
    "they", "he", "she", "it", or "that".

    Do not invent institutional facts.

    If institutional information is required and is not present
    in the supplied knowledge, say:

    "I don't have that information yet."

    Keep the response concise and suitable for speech.
    Prefer 1–3 short sentences.

    VOICE RESPONSE RULES:
- Answer in 1 or 2 sentences.
- Maximum 30 words unless the user explicitly asks for detail.
- Speak naturally.
- No lists.
- No repetition.
- Give only the information needed to answer the question.
    """

        messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            }
        ]

        messages.extend(
            self.get_history(session_id)
        )

        messages.append(
            {
                "role": "user",
                "content": user_prompt,
            }
        )

        # -----------------------------------------
        # STREAM FROM OLLAMA
        # -----------------------------------------

        chunks: list[str] = []

        generation_start = time.perf_counter()

        print(
            f"[CURLY] Starting Ollama stream | "
            f"history={len(messages) - 1} messages | "
            f"prompt_chars={len(user_prompt)}"
        )

        stream_started = time.perf_counter()
        first_token_time = None
        token_count = 0

        async for token in self.llm.generate_stream(
            messages
        ):
            if not token:
                continue

            token_count += 1

            if first_token_time is None:
                first_token_time = (
                    time.perf_counter()
                    - stream_started
                )

                print(
                    f"\n[CURlY] First Ollama token: "
                    f"{first_token_time:.2f}s"
                )

            chunks.append(token)

            yield token

        print(
            f"[CURLY] Ollama stream complete: "
            f"{time.perf_counter() - stream_started:.2f}s | "
            f"tokens: {token_count}"
        )

        # -----------------------------------------
        # SAVE COMPLETE RESPONSE
        # -----------------------------------------

        response_text = "".join(chunks).strip()

        self.save_message(
            session_id,
            "user",
            normalized_text,
        )

        self.save_message(
            session_id,
            "assistant",
            response_text,
        )

        self.set_state(
            session_id,
            CurlyState.SPEAKING,
        )

    # -----------------------------------------
    # EVENTS FROM ANDROID
    # -----------------------------------------

    async def handle_event(
        self,
        session_id: str,
        event: str,
        data: dict,
    ) -> CurlyResponse:

        if event == "AUTH_RESULT":
            return self.handle_auth_result(
                session_id,
                data,
            )

        if event == "TIME_RESULT":
            return self.handle_time_result(
                session_id,
                data,
            )

        if event == "WEATHER_RESULT":
            return self.handle_weather_result(
                session_id,
                data,
            )

        if event == "WAKE_WORD":
            self.set_state(
                session_id,
                CurlyState.AWAKE,
            )

            return CurlyResponse(
                type=ResponseType.RESPONSE,
                command=Command.NONE,
                text="Hey! How can I help?",
                state=CurlyState.AWAKE,
                intent_source=(
                    IntentSource.DETERMINISTIC
                ),
            )

        if event == "LISTENING_STARTED":
            self.set_state(
                session_id,
                CurlyState.LISTENING,
            )

            return CurlyResponse(
                type=ResponseType.RESPONSE,
                command=Command.NONE,
                text="",
                state=CurlyState.LISTENING,
                intent_source=(
                    IntentSource.DETERMINISTIC
                ),
            )

        if event == "LISTENING_STOPPED":
            self.set_state(
                session_id,
                CurlyState.PROCESSING,
            )

            return CurlyResponse(
                type=ResponseType.RESPONSE,
                command=Command.NONE,
                text="",
                state=CurlyState.PROCESSING,
                intent_source=(
                    IntentSource.DETERMINISTIC
                ),
            )

        if event == "TIMEOUT":
            self.set_state(
                session_id,
                CurlyState.IDLE,
            )

            return CurlyResponse(
                type=ResponseType.RESPONSE,
                command=Command.NONE,
                text="",
                state=CurlyState.IDLE,
                intent_source=(
                    IntentSource.DETERMINISTIC
                ),
            )

        if event == "STATE_UPDATE":

            state_value = data.get("state")

            try:
                state = CurlyState(state_value)

                self.set_state(
                    session_id,
                    state,
                )

                return CurlyResponse(
                    type=ResponseType.RESPONSE,
                    command=Command.NONE,
                    text="",
                    state=state,
                    intent_source=None,
                )

            except ValueError:
                self.set_state(
                    session_id,
                    CurlyState.ERROR,
                )

                return CurlyResponse(
                    type=ResponseType.RESPONSE,
                    command=Command.NONE,
                    text="",
                    state=CurlyState.ERROR,
                    intent_source=None,
                )

        return CurlyResponse(
            type=ResponseType.RESPONSE,
            command=Command.NONE,
            text="",
            state=self.get_state(session_id),
            intent_source=None,
        )

    # -----------------------------------------
    # AUTH RESULT
    # -----------------------------------------

    def handle_auth_result(
        self,
        session_id: str,
        data: dict,
    ) -> CurlyResponse:

        status = data.get("status")
        name = data.get("name")

        messages = {
            "AUTHORIZED": (
                f"You're verified. Welcome, {name}!"
                if name
                else "You're verified. Entry permitted."
            ),
            "UNAUTHORIZED": (
                "I'm sorry, you're not authorized "
                "to enter."
            ),
            "UNKNOWN_FACE": (
                "I couldn't identify you. "
                "Please try again."
            ),
            "NO_FACE": (
                "I couldn't see a face. "
                "Please try again."
            ),
            "NETWORK_ERROR": (
                "I'm having trouble reaching "
                "the verification service."
            ),
            "TIMEOUT": (
                "The verification service took "
                "too long to respond."
            ),
            "SERVER_ERROR": (
                "The verification service is "
                "currently unavailable."
            ),
        }

        text = messages.get(
            status,
            "I couldn't complete the verification.",
        )

        self.save_message(
            session_id,
            "assistant",
            text,
        )

        return CurlyResponse(
            type=ResponseType.RESPONSE,
            command=Command.NONE,
            text=text,
            state=CurlyState.SPEAKING,
            intent_source=None,
        )

    # -----------------------------------------
    # TIME RESULT
    # -----------------------------------------

    def handle_time_result(
        self,
        session_id: str,
        data: dict,
    ) -> CurlyResponse:

        current_time = data.get(
            "current_time"
        )

        if not current_time:
            text = (
                "I couldn't get the current time."
            )
        else:
            text = f"It's {current_time}."

        self.save_message(
            session_id,
            "assistant",
            text,
        )

        return CurlyResponse(
            type=ResponseType.RESPONSE,
            command=Command.NONE,
            text=text,
            state=CurlyState.SPEAKING,
            intent_source=None,
        )

    # -----------------------------------------
    # WEATHER RESULT
    # -----------------------------------------

    def handle_weather_result(
        self,
        session_id: str,
        data: dict,
    ) -> CurlyResponse:

        temperature = data.get(
            "temperature"
        )

        condition = data.get(
            "condition"
        )

        if (
            temperature is None
            or not condition
        ):
            text = (
                "I couldn't get the current weather."
            )
        else:
            text = (
                f"It's {temperature} degrees "
                f"and {condition.lower()}."
            )

        self.save_message(
            session_id,
            "assistant",
            text,
        )

        return CurlyResponse(
            type=ResponseType.RESPONSE,
            command=Command.NONE,
            text=text,
            state=CurlyState.SPEAKING,
            intent_source=None,
        )