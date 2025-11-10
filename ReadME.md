#LiveKit Interrupt Handler – Filler vs Intent Detection

Branch: feature/livekit-interrupt-handler-rasagna

##Overview

This branch extends the livekit-agents voice stack with an Interrupt Handler Layer — a lightweight decision module that distinguishes filler speech (hesitation sounds like “uh”, “umm”, “hmm”) from intentional interruption commands (“stop”, “wait”, “no”, “hold on”).

The goal was to make the agent’s conversational flow more human — allowing natural pauses without cutting itself off, while still reacting instantly to explicit user interruptions.

##What Changed
New module: interrupt_filter.py

Implements the core logic that classifies each recognized speech segment as:

IGNORE → filler / hesitation, safe to continue speaking

INTERRUPT → real command to pause or stop agent speech

PASS → normal user input when the agent isn’t speaking

###Key functions added:

class InterruptFilter:
    def __init__(self, fillers: list[str], interrupts: list[str]):
        self.fillers = set(fillers)
        self.interrupts = set(interrupts)

    def decide(self, text: str, confidence: float) -> str:
        # Normalize transcript and decide action type
        if text.lower().strip() in self.fillers:
            return "IGNORE"
        if any(k in text.lower() for k in self.interrupts):
            return "INTERRUPT"
        return "PASS"

Integration points

speech_handle.py

Added a hook to call InterruptFilter.decide() whenever STT returns a transcript chunk.

On "INTERRUPT", it triggers the _interrupt_paused_speech() coroutine.

On "IGNORE", it suppresses further downstream events, preventing speech cutoff.

agent_activity.py

Extended session state tracking with a transient paused_by_user flag.

Added timed auto-resume when the interruption is likely false-positive (e.g., quick noise spike after speech end).

###New runtime parameters
Parameter	Description	Default
ignored_fillers	Comma-separated list of filler tokens to be ignored	"uh,umm,hmm,haan"
interrupt_keywords	Keywords that trigger interruption	"stop,wait,hold on,no,not that"
false_interruption_timeout	Delay (in seconds) before resuming speech after false alarm	1.2

These are read either from .env or as environment variables:

IGNORED_FILLERS="uh,umm,hmm,haan"
INTERRUPT_KEYWORDS="stop,wait,no,hold on"
FALSE_INTERRUPT_TIMEOUT=1.2

##Logic Flow

User audio → STT transcription.

For every interim transcript, InterruptFilter.decide() runs.

If IGNORE, event suppressed and agent continues speaking.

If INTERRUPT, agent speech paused via SpeechHandle.stop() and _interrupt_paused_speech() scheduled.

If PASS, forwarded as a normal user utterance.

Optional false-interruption timer resumes agent if no further input detected.

##Testing
Manual testing

Ran the agent locally using:

python .\examples\voice_agents\basic_agent.py console


Simulated sessions using console mic and sample recordings.

Scenario	Expected	Observed
User says “uh” or “umm” mid-agent speech	Continue without interruption	✅ Works as expected
User says “wait” while agent speaks	Agent stops instantly	✅ Works
Filler immediately followed by command (“umm stop”)	Treats as interrupt	✅ Works
Random background noise or laughter	No false trigger	✅ Mostly stable (1 false positive in 10 tests)
Long pause after false interrupt	Agent resumes automatically after 1.2s	✅ Works
Automated unit testing

Added a minimal sanity test (quick_interrupt_test.py) verifying:

assert f.decide("uh", 0.92) == "IGNORE"
assert f.decide("stop please", 0.85) == "INTERRUPT"
assert f.decide("how are you", 0.97) == "PASS"

##Known Issues

ONNXRuntime long path bug (Windows):
Installing livekit-plugins-silero may fail due to deep directory paths.
Workaround: move the project to C:\lk\livekit-agents or enable long paths via registry.

Edge-case overlap:
Phrases like “no worries” can trigger interrupts incorrectly. Plan to refine with token-based context matching.

Limited test coverage on Linux/macOS audio pipelines.

##How to Run / Steps to Test
1. Environment setup
python -m venv .venv
.\.venv\Scripts\activate
pip install -U pip setuptools wheel
pip install -e .
pip install python-dotenv
pip install "livekit-plugins-silero"

2. Run local agent
python .\examples\voice_agents\basic_agent.py console

3. (Optional) connect to LiveKit dev server
.\livekit-server.exe --dev
setx LIVEKIT_URL "ws://localhost:7880"
setx LIVEKIT_API_KEY "devkey"
setx LIVEKIT_API_SECRET "secret"

##Environment Details
Component	Version
OS	Windows 11
Python	3.13.7
Dependencies	livekit-agents, livekit-plugins-silero, onnxruntime, python-dotenv
Entry Point	examples/voice_agents/basic_agent.py
🚀 Summary

This branch adds an intelligent, speech-aware interruption layer that allows the LiveKit voice agent to handle natural human hesitations gracefully.
Instead of stopping for every “uh” or “umm,” it now waits intelligently — only responding when the user clearly signals an intent to interrupt.

This change significantly improves the naturalness and robustness of voice interactions in dynamic conversations.
