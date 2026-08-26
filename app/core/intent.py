from app.models.schemas import Command


class IntentResult:

    def __init__(
        self,
        command: Command,
        confidence: float,
    ):
        self.command = command
        self.confidence = confidence


def detect_command(text: str) -> IntentResult | None:

    text = text.lower().strip()

    # -----------------------------------------
    # FACE AUTHENTICATION
    # -----------------------------------------

    authentication_phrases = [
        "verify me",
        "authenticate me",
        "check my identity",
        "check my id",
        "scan my face",
        "scan me",
        "check me",
        "recognize me",
        "recognise me",
        "let me in",
        "can i enter",
        "can i get in",
        "open the door",
        "unlock the door",
        "check if i can enter",
        "check whether i can enter",
        "check if i'm allowed in",
        "check if i am allowed in",
        "i need access",
        "i need to get inside",
        "i need to enter"
    ]

    if any(
        phrase in text
        for phrase in authentication_phrases
    ):
        return IntentResult(
            Command.FACE_AUTH,
            1.0
        )

    # -----------------------------------------
    # TIME
    # -----------------------------------------

    time_phrases = [
        "what time is it",
        "what's the time",
        "whats the time",
        "tell me the time",
        "current time",
        "time right now"
    ]

    if any(
        phrase in text
        for phrase in time_phrases
    ):
        return IntentResult(
            Command.GET_TIME,
            1.0
        )

    # -----------------------------------------
    # WEATHER
    # -----------------------------------------

    weather_phrases = [
        "what's the weather",
        "whats the weather",
        "current weather",
        "weather like",
        "how is the weather",
        "how's the weather",
        "hows the weather"
    ]

    if any(
        phrase in text
        for phrase in weather_phrases
    ):
        return IntentResult(
            Command.GET_WEATHER,
            1.0
        )

        # -----------------------------------------
    # LAB INFORMATION
    # -----------------------------------------

    lab_phrases = [
        "what is the lab",
        "what is the laboratory",
        "tell me about the lab",
        "tell me about the laboratory",

        "lab opening time",
        "lab closing time",

        "when does the lab open",
        "when does the lab close",

        "when does the laboratory open",
        "when does the laboratory close",

        "what time does the lab open",
        "what time does the lab close",

        "what time does the laboratory open",
        "what time does the laboratory close",

        "where is the lab",
        "where is the laboratory",

        "who is the lab in-charge",
        "who is in charge of the lab",
        "who's in charge of the lab",

        "who is the laboratory in-charge",
        "who is in charge of the laboratory",
        "who's in charge of the laboratory",

        "lab in-charge",
        "lab incharge",
        "laboratory in-charge",
        "laboratory incharge",

        "laboratory opening time",
        "laboratory closing time"
    ]

    if any(
        phrase in text
        for phrase in lab_phrases
    ):
        return IntentResult(
            Command.GET_LAB_INFO,
            1.0
        )

    # -----------------------------------------
    # END CONVERSATION
    # -----------------------------------------

    end_phrases = [
        "goodbye",
        "good bye",
        "bye curly",
        "that's all",
        "thats all",
        "stop talking",
        "you can go",
        "see you later"
    ]

    if any(
        phrase in text
        for phrase in end_phrases
    ):
        return IntentResult(
            Command.END_CONVERSATION,
            1.0
        )

    return None