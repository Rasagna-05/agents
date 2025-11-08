# interrupt_filter.py
import os
import re
import logging
from typing import Optional

class Decision:
    IGNORE = "ignore"  # drop this ASR chunk silently
    STOP = "stop"      # valid interruption -> stop agent TTS immediately
    PASS = "pass"      # treat as normal speech

def _read_list(env_key: str, default_csv: str) -> list[str]:
    raw = os.getenv(env_key, default_csv)
    parts = re.split(r"[,\s]+", raw)
    return [p.strip().lower() for p in parts if p.strip()]

class InterruptFilter:
    """
    Stateless text/score checker + speaking state latch you control via set_agent_speaking().
    """
    def __init__(self) -> None:
        self.log = logging.getLogger("interrupt_filter")

        # Config via env; defaults match the assignment brief
        self.ignored_words = _read_list("IGNORED_FILLERS", "uh,umm,hmm,haan")
        self.interrupt_keywords = _read_list(
            "INTERRUPT_KEYWORDS", "stop,wait,hold on,one second,listen,no,not that"
        )
        self.min_conf_while_speaking = float(os.getenv("MIN_CONF_WHILE_SPEAKING", "0.65"))
        self.min_conf_when_quiet = float(os.getenv("MIN_CONF_WHEN_QUIET", "0.25"))
        self.max_filler_len = int(os.getenv("MAX_FILLER_LEN", "12"))

        self._filler_re = re.compile(
            r"^(?:{})(?:[.!?,\s]*)$".format("|".join(re.escape(w) for w in self.ignored_words)),
            flags=re.IGNORECASE,
        )
        self._kw_re = re.compile(
            r"\b(?:{})\b".format("|".join(re.escape(w) for w in self.interrupt_keywords)),
            flags=re.IGNORECASE,
        )
        self._agent_speaking = False

    def set_agent_speaking(self, speaking: bool) -> None:
        self._agent_speaking = speaking

    def decide(self, text: str, confidence: Optional[float]) -> str:
        if text is None:
            return Decision.IGNORE
        s = text.strip()
        if not s:
            return Decision.IGNORE
        conf = 1.0 if confidence is None else float(confidence)

        if self._agent_speaking:
            # 1) Hard interrupt words always STOP
            if self._kw_re.search(s):
                self.log.info("VALID INTERRUPTION (keyword during TTS): %r", s)
                return Decision.STOP

            # 2) Low-confidence & filler-only -> IGNORE
            if conf < self.min_conf_while_speaking and self._filler_re.match(s):
                self.log.info("IGNORED (low-conf filler during TTS): %r (%.2f)", s, conf)
                return Decision.IGNORE

            # 3) Filler-only & short -> IGNORE
            if self._filler_re.match(s) and len(s) <= self.max_filler_len:
                self.log.info("IGNORED (filler during TTS): %r", s)
                return Decision.IGNORE

            # 4) Anything else while TTS -> STOP (real interruption)
            self.log.info("VALID INTERRUPTION (speech during TTS): %r (%.2f)", s, conf)
            return Decision.STOP

        # Agent quiet: register speech (even fillers), except ultra-low-conf pure filler
        if conf < self.min_conf_when_quiet and self._filler_re.match(s):
            self.log.info("IGNORED (ultra-low-conf while quiet): %r (%.2f)", s, conf)
            return Decision.IGNORE

        return Decision.PASS
