from app.core.intent import detect_command
from app.models.schemas import Command


def test_face_auth():

    result = detect_command(
        "Verify me"
    )

    assert result is not None
    assert result.command == Command.FACE_AUTH


def test_face_auth_scan():

    result = detect_command(
        "Scan my face"
    )

    assert result is not None
    assert result.command == Command.FACE_AUTH


def test_time():

    result = detect_command(
        "What time is it?"
    )

    assert result is not None
    assert result.command == Command.GET_TIME


def test_weather():

    result = detect_command(
        "What's the weather?"
    )

    assert result is not None
    assert result.command == Command.GET_WEATHER


def test_goodbye():

    result = detect_command(
        "Goodbye Curly"
    )

    assert result is not None
    assert result.command == Command.END_CONVERSATION


def test_normal_conversation():

    result = detect_command(
        "How are you?"
    )

    assert result is None

def test_face_auth_variations():

    phrases = [
        "Can you check my identity?",
        "I need to get inside, can you scan me?",
        "Could you authenticate me?",
        "Can I enter?",
        "Please recognize me",
        "I need access, check me"
    ]

    for text in phrases:

        result = detect_command(text)

        assert result is not None
        assert result.command == Command.FACE_AUTH

def test_lab_information():

    phrases = [
        "When does the lab open?",
        "When does the lab close?",
        "Where is the lab?",
        "Who is the lab in-charge?",
        "What time does the laboratory close?"
    ]

    for text in phrases:

        result = detect_command(text)

        assert result is not None
        assert result.command == Command.GET_LAB_INFO


def test_lab_mention_is_not_lab_command():

    phrases = [
        "How are things at the lab?",
        "I'm working in the lab today.",
        "Is everyone at the lab?"
    ]

    for text in phrases:

        result = detect_command(text)

        assert result is None