import ast
import inspect
import unittest
from unittest.mock import patch
from tests.e2e import native_voice_reference as reference

class ReferenceContract(unittest.TestCase):
    def test_live_disabled_by_default(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "not authorized"):
                reference.require_live_authorization()

    def test_explicit_permission_without_credentials_is_insufficient(self):
        with patch.dict("os.environ", {"GRAVITRE_REFERENCE_LIVE": "1"}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "Missing reference configuration"):
                reference.require_live_authorization()

    def test_no_gravitre_runtime_dependencies(self):
        tree = ast.parse(inspect.getsource(reference))
        names = [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
        names += [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
        self.assertFalse(any(n.startswith(("app.", "supabase", "livekit")) for n in names))

    def test_pinned_native_sdk_symbols(self):
        from pipecat.runner.types import SmallWebRTCRunnerArguments
        from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport
        from pipecat.services.deepgram.flux.stt import DeepgramFluxSTTService
        from pipecat.services.openai.llm import OpenAILLMService
        from pipecat.services.elevenlabs.tts import ElevenLabsTTSService
        from pipecat.turns.user_turn_strategies import ExternalUserTurnStrategies
        for cls in (SmallWebRTCRunnerArguments, SmallWebRTCTransport, DeepgramFluxSTTService, OpenAILLMService, ElevenLabsTTSService, ExternalUserTurnStrategies):
            self.assertTrue(callable(cls))

if __name__ == "__main__":
    unittest.main()
