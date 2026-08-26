import os
import tempfile
import time
import wave
from pathlib import Path
import re

import sounddevice as sd

from app.core.curly import Curly, CurlyState
from app.models.schemas import Command
from app.stt.service import STTService
from app.tts.service import TTSService


class CurlyVoiceEngine:

    def __init__(
        self,
        curly: Curly,
        stt: STTService,
        tts: TTSService,
        sample_rate: int = 16000,
        wake_phrase: str = "hey curly",
        silence_seconds: float = 1.2,
        max_record_seconds: float = 6.0,
        session_timeout_seconds: int = 300,
    ):

        self.curly = curly
        self.stt = stt
        self.tts = tts

        self.sample_rate = sample_rate
        self.wake_phrase = wake_phrase.lower()

        self.silence_seconds = silence_seconds
        self.max_record_seconds = max_record_seconds
        self.session_timeout_seconds = (
            session_timeout_seconds
        )

        self.session_id = (
            self.curly.create_session()
        )

        self.active = False
        self.last_activity = time.monotonic()

    # --------------------------------------------------
    # AUDIO RECORDING
    # --------------------------------------------------

    def record_audio(
        self,
        duration: float,
    ) -> Path:

        frames = int(
            duration * self.sample_rate
        )

        recording = sd.rec(
            frames,
            samplerate=self.sample_rate,
            channels=1,
            dtype="int16",
        )

        sd.wait()

        temp = tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".wav",
        )

        temp.close()

        with wave.open(
            temp.name,
            "wb",
        ) as wav:

            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(
                self.sample_rate
            )

            wav.writeframes(
                recording.tobytes()
            )

        return Path(temp.name)

    # --------------------------------------------------
    # SPEECH PLAYBACK
    # --------------------------------------------------

    def play_audio(
        self,
        audio_path: Path,
    ):

        # macOS development playback
        os.system(
            f'afplay "{audio_path}"'
        )

    # --------------------------------------------------
    # STT
    # --------------------------------------------------

    def transcribe(
        self,
        audio_path: Path,
    ) -> str:

        result = self.stt.transcribe(
            str(audio_path)
        )

        if not result:
            return ""

        return result.get(
            "text",
            "",
        ).strip()

    # --------------------------------------------------
    # WAKE WORD
    # --------------------------------------------------

    def check_wake_word(
        self,
        text: str,
    ) -> bool:
        
        normalized = re.sub(
            r"[^a-zA-Z0-9\s]",
            "",
            text.lower()
        )

        normalized = " ".join(
            normalized.split()
        )

        return (
            self.wake_phrase
            in normalized
        )

    # --------------------------------------------------
    # PLAY SPOKEN RESPONSE
    # --------------------------------------------------

    async def speak(
        self,
        text: str,
    ):

        if not text:
            return

        audio_path = await self.tts.synthesize(
            text
        )

        try:

            self.play_audio(
                audio_path
            )

        finally:

            try:
                audio_path.unlink(
                    missing_ok=True
                )
            except OSError:
                pass

    # --------------------------------------------------
    # PROCESS USER REQUEST
    # --------------------------------------------------

    async def process_request(
        self,
        text: str,
    ):

        self.last_activity = time.monotonic()

        response = await self.curly.chat(
            session_id=self.session_id,
            text=text,
        )

        self.curly.set_state(
            self.session_id,
            response.state,
        )

        await self.speak(
            response.text
        )

        return response

    # --------------------------------------------------
    # AUTHENTICATION RESULT
    # --------------------------------------------------

    async def handle_auth_result(
        self,
        status: str,
        name: str | None = None,
    ):

        response = self.curly.handle_auth_result(
            self.session_id,
            {
                "status": status,
                "name": name,
            },
        )

        print(
            f"Curly: {response.text}"
        )

        await self.speak(
            response.text
        )

        self.last_activity = (
            time.monotonic()
        )

        self.curly.set_state(
            self.session_id,
            CurlyState.LISTENING,
        )

        self.active = True

    # --------------------------------------------------
    # CONVERSATION LOOP
    # --------------------------------------------------

    async def run(self):

        print()
        print("================================")
        print("        CURLY VOICE ENGINE")
        print("================================")
        print()
        print("Waiting for 'Hey Curly'...")
        print()

        while True:

            # ------------------------------------------
            # IDLE / WAKE LISTENING
            # ------------------------------------------

            wake_audio = self.record_audio(
                duration=2.0
            )

            try:

                try:

                    wake_text = self.transcribe(
                        wake_audio
                    )

                except ValueError:

                    # Ignore non-English wake audio.
                    wake_text = ""

                except RuntimeError as error:

                    print(
                        f"Wake STT error: {error}"
                    )

                    wake_text = ""

            finally:

                wake_audio.unlink(
                    missing_ok=True
                )

            if not wake_text:
                continue

            print(
                f"[wake listener] {wake_text}"
            )

            if not self.check_wake_word(
                wake_text
            ):
                
                print(
                    "[wake listener] Wake phrase not detected."
                )

                continue

            print(
                "[wake listener] Wake phrase detected."
            )

            # ------------------------------------------
            # WAKE
            # ------------------------------------------

            self.active = True
            self.last_activity = (
                time.monotonic()
            )

            self.curly.set_state(
                self.session_id,
                CurlyState.AWAKE,
            )

            print(
                "Curly: Hey! How can I help?"
            )

            await self.speak(
                "Hey! How can I help?"
            )

            # ------------------------------------------
            # ACTIVE CONVERSATION
            # ------------------------------------------

            while self.active:

                # --------------------------------------
                # SESSION TIMEOUT
                # --------------------------------------

                if (
                    time.monotonic()
                    - self.last_activity
                    > self.session_timeout_seconds
                ):

                    self.active = False

                    self.curly.set_state(
                        self.session_id,
                        CurlyState.IDLE,
                    )

                    print(
                        "Conversation timed out."
                    )

                    break

                # --------------------------------------
                # LISTENING
                # --------------------------------------

                self.curly.set_state(
                    self.session_id,
                    CurlyState.LISTENING,
                )

                print(
                    "Listening..."
                )

                request_audio = self.record_audio(
                    duration=self.max_record_seconds
                )

                try:

                    try:

                        text = self.transcribe(
                            request_audio
                        )

                    except ValueError:

                        print(
                            "Curly: Please speak in English."
                        )

                        await self.speak(
                            "Please speak in English."
                        )

                        self.last_activity = (
                            time.monotonic()
                        )

                        continue

                    except RuntimeError as error:

                        print(
                            f"STT error: {error}"
                        )

                        continue

                finally:

                    request_audio.unlink(
                        missing_ok=True
                    )

                if not text:
                    continue

                print(
                    f"You: {text}"
                )

                # --------------------------------------
                # CURLY
                # --------------------------------------

                try:

                    response = await self.process_request(
        text
    )

                except Exception as error:

                    print(
        f"Curly processing error: {error}"
    )

                    self.curly.set_state(
                    self.session_id,
                    CurlyState.ERROR
    )

                    try:

                        await self.speak(
            "I'm having trouble connecting to my AI system."
        )

                    except Exception:
                        pass

                    self.last_activity = (
        time.monotonic()
    )

                    continue

                print(
                    f"Curly: {response.text}"
                )

                # --------------------------------------
                # FACE AUTHENTICATION HANDOFF
                # --------------------------------------

                if (
                    response.command
                    == Command.FACE_AUTH
                ):

                    self.active = False

                    self.curly.set_state(
                        self.session_id,
                        CurlyState.AUTHENTICATING,
                    )

                    print()
                    print(
                        "FACE_AUTH requested."
                    )
                    print(
                        "Waiting for authentication result..."
                    )
                    print()

                    return

                # --------------------------------------
                # END CONVERSATION
                # --------------------------------------

                if (
                    response.state
                    == CurlyState.IDLE
                ):

                    self.active = False

                    print(
                        "Curly returned to idle."
                    )

                    break