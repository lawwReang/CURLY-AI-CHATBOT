import uuid

from app.config import settings
from app.core.intent import detect_command
from app.core.llm_response import LLMResponseGenerator
from app.core.prompts import SYSTEM_PROMPT
from app.core.session import Session
from app.llm.ollama import OllamaClient

from app.models.schemas import (
    Command,
    CurlyResponse,
    CurlyState,
    IntentSource,
    ResponseType
)

from app.models.schemas import (
    Command,
    CurlyResponse,
    CurlyState,
    IntentSource,
    ResponseType
)


class Curly:

    def __init__(
        self,
        llm: OllamaClient,
        knowledge
    ):

        self.llm = llm
        self.knowledge = knowledge

        self.response_generator = (
          LLMResponseGenerator(llm)
        )

        self.sessions: dict[
            str,
            Session
        ] = {}

    # -----------------------------------------
    # SESSION
    # -----------------------------------------

    def create_session(self) -> str:

     self.cleanup_expired_sessions()

     session_id = str(
         uuid.uuid4()
     )

     self.sessions[session_id] = Session(
         session_id=session_id
     )

     return session_id
    
    def get_session(
        self,
        session_id: str
    ) -> Session:
        
        session = self.sessions.get(
            session_id
        )

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
          session_id: str
     ):

          return self.get_session(
               session_id
          ).history

    def save_message(
        self,
        session_id: str,
        role: str,
        content: str
    ):

        history = self.get_history(
            session_id
        )

        history.append({
            "role": role,
            "content": content
        })

        max_messages = (
            settings.max_history * 2
        )

        if len(history) > max_messages:

            del history[:-max_messages]

    def clear_session(
        self,
        session_id: str
    ):

        self.sessions.pop(
            session_id,
            None
          )

    def set_state(
          self,
          session_id: str,
          state: CurlyState
     ):

          session = self.get_session(
               session_id
          )

          session.set_state(state)

    def get_state(
          self,
          session_id: str
     ) -> CurlyState:

          session = self.get_session(
               session_id
          )

          return session.state
    
    def cleanup_expired_sessions(self):

     expired_ids = []

     for session_id, session in self.sessions.items():

        if session.is_expired(
            settings.session_timeout_seconds
        ):
            expired_ids.append(
                session_id
            )

     for session_id in expired_ids:

        del self.sessions[session_id]

    def detect_knowledge_topic(
     self,
     text: str
    ) -> str | None:

     text = text.lower()

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
        "assam don bosco university"
     ]

     lab_terms = [
        "lab",
        "laboratory",
        "lab in-charge",
        "lab incharge",
        "opening time",
        "closing time"
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
    # COMMAND RESPONSE
    # -----------------------------------------

    def command_response(
          self,
          command: Command,
          source: IntentSource
     ) -> CurlyResponse:

          responses = {

          Command.FACE_AUTH:
            "Sure! I'll verify you.",

          Command.GET_TIME:
            "Let me check the current time.",

          Command.GET_WEATHER:
            "Let me check the current weather.",

          Command.GET_LAB_INFO:
            "Sure, let me check that.",

          Command.END_CONVERSATION:
            "Alright. See you later!"
          }

          states = {

               Command.FACE_AUTH:
                CurlyState.AUTHENTICATING,

               Command.END_CONVERSATION:
                CurlyState.IDLE,

               Command.GET_TIME:
                CurlyState.SPEAKING,

               Command.GET_WEATHER:
                CurlyState.SPEAKING,

               Command.GET_LAB_INFO:
                CurlyState.SPEAKING
          }
          return CurlyResponse(
               type=ResponseType.COMMAND,
               command=command,
               text=responses.get(
                    command,
                    "Sure."
          ),
          state=states.get(
            command,
            CurlyState.SPEAKING
        ),
        intent_source=source
     )

    # -----------------------------------------
    # MAIN CHAT
    # -----------------------------------------

    async def chat(
        self,
        session_id: str,
        text: str,
        context: dict | None = None
    ) -> CurlyResponse:
        
        session = self.get_session(
          session_id
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
            # KNOWLEDGE INTENT
            # ---------------------------------

            if detected.command == Command.GET_LAB_INFO:

                self.set_state(
                    session_id,
                    CurlyState.PROCESSING
                )

                knowledge_context = (
                    self.knowledge.get_context("lab")
                )

                user_prompt = f"""
RELEVANT INSTITUTIONAL INFORMATION:

{knowledge_context}

USER QUESTION:

{text}

Answer using only the supplied institutional information.

Never invent institutional facts.

If the information is not present, say:
"I don't have that information yet."

Keep the answer concise and natural because it will be spoken aloud.
"""

                messages = [
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT
                    }
                ]

                messages.extend(
                    self.get_history(session_id)
                )

                messages.append({
                    "role": "user",
                    "content": user_prompt
                })

                response = await self.llm.generate(
                    messages
                )

                response = response.strip()

                self.save_message(
                    session_id,
                    "user",
                    text
                )

                self.save_message(
                    session_id,
                    "assistant",
                    response
                )

                self.set_state(
                    session_id,
                    CurlyState.SPEAKING
                )

                return CurlyResponse(
                    type=ResponseType.RESPONSE,
                    command=Command.NONE,
                    text=response,
                    state=CurlyState.SPEAKING,
                    intent_source=(
                        IntentSource.DETERMINISTIC
                    )
                )

            # ---------------------------------
            # NORMAL APPLICATION COMMAND
            # ---------------------------------

            result = self.command_response(
                detected.command,
                IntentSource.DETERMINISTIC
            )

            self.save_message(
                session_id,
                "user",
                text
            )

            self.save_message(
                session_id,
                "assistant",
                result.text
            )

            self.set_state(
                session_id,
                result.state
            )

            return result

                # -------------------------------------
        # 2. KNOWLEDGE CONTEXT
        # -------------------------------------

        topic = self.detect_knowledge_topic(
            text
        )

        if topic:

            knowledge_context = (
                self.knowledge.get_context(
                    topic
                )
            )

        else:

            knowledge_context = ""

        # -------------------------------------
        # 3. SINGLE LLM DECISION + RESPONSE
        # -------------------------------------

        decision = await self.response_generator.generate(
            user_text=text,
            history=self.get_history(
                session_id
            ),
            knowledge_context=knowledge_context,
            environment_context=context
        )

        # -------------------------------------
        # 4. LLM COMMAND
        # -------------------------------------

        if (
            decision.type == ResponseType.COMMAND
            and decision.command != Command.NONE
            and decision.confidence >= 0.80
        ):

            if decision.command == Command.FACE_AUTH:

                state = CurlyState.AUTHENTICATING

            elif (
                decision.command
                == Command.END_CONVERSATION
            ):

                state = CurlyState.IDLE

            else:

                state = CurlyState.SPEAKING

            result = CurlyResponse(
                type=ResponseType.COMMAND,
                command=decision.command,
                text=decision.text,
                state=state,
                intent_source=IntentSource.LLM
            )

            self.save_message(
                session_id,
                "user",
                text
            )

            self.save_message(
                session_id,
                "assistant",
                decision.text
            )

            self.set_state(
                session_id,
                state
            )

            return result

        # -------------------------------------
        # 5. NORMAL LLM RESPONSE
        # -------------------------------------

        self.save_message(
            session_id,
            "user",
            text
        )

        self.save_message(
            session_id,
            "assistant",
            decision.text
        )

        self.set_state(
            session_id,
            CurlyState.SPEAKING
        )

        return CurlyResponse(
            type=ResponseType.RESPONSE,
            command=Command.NONE,
            text=decision.text,
            state=CurlyState.SPEAKING,
            intent_source=None
        )

    # -----------------------------------------
    # EVENTS FROM ANDROID
    # -----------------------------------------

    async def handle_event(
        self,
        session_id: str,
        event: str,
        data: dict
    ) -> CurlyResponse:

        if event == "AUTH_RESULT":

            return self.handle_auth_result(
                session_id,
                data
            )

        if event == "TIME_RESULT":

            return self.handle_time_result(
                session_id,
                data
            )

        if event == "WEATHER_RESULT":

            return self.handle_weather_result(
                session_id,
                data
            )
        
        if event == "WAKE_WORD":

         self.set_state(
          session_id,
          CurlyState.AWAKE
         )

         return CurlyResponse(
          type=ResponseType.RESPONSE,
          command=Command.NONE,
          text="Hey! How can I help?",
          state=CurlyState.AWAKE,
          intent_source=IntentSource.DETERMINISTIC
        )
        

        if event == "LISTENING_STARTED":

         self.set_state(
          session_id,
          CurlyState.LISTENING
         )

         return CurlyResponse(
          type=ResponseType.RESPONSE,
          command=Command.NONE,
          text="",
          state=CurlyState.LISTENING,
          intent_source=IntentSource.DETERMINISTIC
        )

        if event == "LISTENING_STOPPED":

         self.set_state(
        session_id,
        CurlyState.PROCESSING
    )

         return CurlyResponse(
        type=ResponseType.RESPONSE,
        command=Command.NONE,
        text="",
        state=CurlyState.PROCESSING,
        intent_source=IntentSource.DETERMINISTIC
    )
        
        if event == "TIMEOUT":

         self.set_state(
        session_id,
        CurlyState.IDLE
    )

         return CurlyResponse(
        type=ResponseType.RESPONSE,
        command=Command.NONE,
        text="",
        state=CurlyState.IDLE,
        intent_source=IntentSource.DETERMINISTIC
    )

        if event == "STATE_UPDATE":

          state_value = data.get(
               "state"
          )

          try:

               state = CurlyState(
                    state_value
               )

               self.set_state(
                    session_id,
                    state
               )

               return CurlyResponse(
                    type=ResponseType.RESPONSE,
                    command=Command.NONE,
                    text="",
                    state=state,
                    intent_source=None
               )

          except ValueError:

               self.set_state(
                   session_id,
                   CurlyState.ERROR
               )

               return CurlyResponse(
                    type=ResponseType.RESPONSE,
                    command=Command.NONE,
                    text="",
                    state=CurlyState.ERROR,
                    intent_source=None
               )

        return CurlyResponse(
            type=ResponseType.RESPONSE,
            command=Command.NONE,
            text="",
            state=self.get_state(session_id),
            intent_source=None
        )

    # -----------------------------------------
    # AUTH RESULT
    # -----------------------------------------

    def handle_auth_result(
        self,
        session_id: str,
        data: dict
    ) -> CurlyResponse:

        status = data.get(
            "status"
        )

        name = data.get(
            "name"
        )

        messages = {

            "AUTHORIZED":
                f"You're verified. Welcome, {name}!"
                if name
                else "You're verified. Entry permitted.",

            "UNAUTHORIZED":
                "I'm sorry, you're not authorized to enter.",

            "UNKNOWN_FACE":
                "I couldn't identify you. Please try again.",

            "NO_FACE":
                "I couldn't see a face. Please try again.",

            "NETWORK_ERROR":
                "I'm having trouble reaching the verification service.",

            "TIMEOUT":
                "The verification service took too long to respond.",

            "SERVER_ERROR":
                "The verification service is currently unavailable."
        }

        text = messages.get(
            status,
            "I couldn't complete the verification."
        )

        self.save_message(
            session_id,
            "assistant",
            text
        )

        return CurlyResponse(
            type=ResponseType.RESPONSE,
            command=Command.NONE,
            text=text,
            state=CurlyState.SPEAKING,
            intent_source=None
        )

    # -----------------------------------------
    # TIME RESULT
    # -----------------------------------------

    def handle_time_result(
        self,
        session_id: str,
        data: dict
    ) -> CurlyResponse:

        current_time = data.get(
            "current_time"
        )

        if not current_time:

            text = "I couldn't get the current time."

        else:

            text = (
                f"It's {current_time}."
            )

        self.save_message(
            session_id,
            "assistant",
            text
        )

        return CurlyResponse(
            type=ResponseType.RESPONSE,
            command=Command.NONE,
            text=text,
            state=CurlyState.SPEAKING,
            intent_source=None
        )

    # -----------------------------------------
    # WEATHER RESULT
    # -----------------------------------------

    def handle_weather_result(
        self,
        session_id: str,
        data: dict
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
            text
        )

        return CurlyResponse(
            type=ResponseType.RESPONSE,
            command=Command.NONE,
            text=text,
            state=CurlyState.SPEAKING,
            intent_source=None
        )
    