"""
Centralised logging setup.

Goal: the terminal stays clean — only useful run progress, summaries, warnings and
errors — while the FULL detailed log (DEBUG + third-party chatter) is written to a
timestamped file under logs/.

Call setup_logging() ONCE, as early as possible in an entry point (before importing
heavy modules / constructing the vector DB), e.g.:

    from scripts.common_stuff.logging_setup import setup_logging
    log_file = setup_logging()            # clean console + logs/<name>_run_<ts>.log
    setup_logging(console_level=logging.DEBUG)   # verbose console (debugging)
"""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Libraries that flood the terminal with INFO/DEBUG noise. Pinned to WARNING on
# console+file (their genuine warnings/errors still surface).
_NOISY_LOGGERS = [
    "sentence_transformers", "transformers", "chromadb",
    "httpx", "httpcore", "urllib3", "asyncio", "PIL", "playwright",
    "filelock", "numexpr", "matplotlib", "fsspec", "datasets",
]

# These warn even at WARNING level (e.g. HF "unauthenticated requests" / no HF_TOKEN)
# and attach their own handler that propagates — pin to ERROR and stop propagation.
_SILENCE_TO_ERROR = ["huggingface_hub", "transformers.modeling_utils"]


# Benign lines some compiled ML extensions write straight to stderr (bypassing
# Python logging/warnings). Dropped from the terminal; nothing else is touched.
_BENIGN_STDERR = (
    "unauthenticated requests to the HF Hub",
    "Please set a HF_TOKEN",
    "Loading weights",
    "BertModel LOAD REPORT",
    "Batches:",
    "embeddings.position_ids",
    "can be ignored when loading",
    "UNEXPECTED",
)


class _StderrLineFilter:
    """Line-buffered stderr proxy that suppresses known-benign noise lines."""

    def __init__(self, stream):
        self._s = stream
        self._buf = ""

    def write(self, text):
        self._buf += text
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            if not any(b in line for b in _BENIGN_STDERR):
                self._s.write(line + "\n")
        return len(text)

    def flush(self):
        if self._buf and not any(b in self._buf for b in _BENIGN_STDERR):
            self._s.write(self._buf)
            self._buf = ""
        self._s.flush()

    def __getattr__(self, name):
        return getattr(self._s, name)


class _CleanConsoleFormatter(logging.Formatter):
    """Terminal formatter: bare message for INFO, flagged for WARNING/ERROR."""

    def format(self, record):
        msg = record.getMessage()
        if record.levelno >= logging.ERROR:
            return f"❌ {msg}"
        if record.levelno >= logging.WARNING:
            return f"⚠️  {msg}"
        return msg


def _quiet_third_party_progress():
    """Disable HuggingFace/transformers progress bars and load reports."""
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
    os.environ.setdefault("TRANSFORMERS_NO_ADVISORY_WARNINGS", "1")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    # sentence-transformers shows its "Batches:" tqdm bar only when its logger is
    # at INFO — pinning it to WARNING (below) suppresses the bar too.


def setup_logging(console_level: int = logging.INFO,
                  log_dir: str = "logs",
                  run_name: str = "naukri") -> str:
    """
    Configure root logging: clean console + full file log. Returns the log path.

    Safe to call more than once (it rebuilds handlers each time).
    """
    _quiet_third_party_progress()

    # Drop benign compiled-extension noise written directly to stderr.
    if not isinstance(sys.stderr, _StderrLineFilter):
        sys.stderr = _StderrLineFilter(sys.stderr)

    Path(log_dir).mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = Path(log_dir) / f"{run_name}_run_{ts}.log"

    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
    root.setLevel(logging.DEBUG)  # capture all; per-handler levels filter output

    # Full detail → file
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"))
    root.addHandler(fh)

    # Curated, clean → terminal
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(console_level)
    ch.setFormatter(_CleanConsoleFormatter())
    root.addHandler(ch)

    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)

    for name in _SILENCE_TO_ERROR:
        lg = logging.getLogger(name)
        lg.setLevel(logging.ERROR)
        lg.propagate = False
        for h in list(lg.handlers):
            lg.removeHandler(h)

    # The HF token notice is also raised via the warnings module on some versions.
    import warnings
    warnings.filterwarnings("ignore", message=".*unauthenticated requests.*")
    warnings.filterwarnings("ignore", message=".*HF_TOKEN.*")

    logging.getLogger(__name__).debug(f"Logging initialised → {log_path}")
    return str(log_path)
