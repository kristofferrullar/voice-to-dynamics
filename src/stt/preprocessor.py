"""Swedish speech preprocessor.

Strips hesitation sounds and filler words from transcribed speech so the
agent receives clean, intent-bearing text.

Examples:
  "Emh, hur många öppna affärsmöjligheter, liksom, har jag?"
  → "Hur många öppna affärsmöjligheter har jag?"

  "Kan du kan du visa mina leads?"
  → "Kan du visa mina leads?"
"""
import re


# Hesitation sounds (language-agnostic enough to be safe to strip unconditionally)
_HESITATIONS = re.compile(
    r"\b(emh|öh|eh|ah|uhh|mm+|hmm+|ehm|äh|ähm)\b",
    re.IGNORECASE,
)

# Swedish filler words — stripped only at utterance boundaries or between clauses
# to avoid accidentally removing meaningful words.
_FILLERS = re.compile(
    r"\b(liksom|alltså|typ|ba|asså|nånting|liksom sagt|va)\b",
    re.IGNORECASE,
)

# Consecutive word repetitions: "kan du kan du" → "kan du"
_REPETITION = re.compile(
    r"\b(\w+(?:\s+\w+){0,3})\s+\1\b",
    re.IGNORECASE,
)

# Multiple spaces / leading-trailing whitespace
_SPACES = re.compile(r"\s{2,}")

# Trailing punctuation left by removals
_ORPHAN_PUNCT = re.compile(r"\s+([,.])")


class SwedishPreprocessor:
    """Remove Swedish filler words and hesitations from STT output."""

    def clean(self, text: str) -> str:
        text = _HESITATIONS.sub("", text)
        text = _FILLERS.sub("", text)
        # Collapse repetitions (run twice to catch overlapping patterns)
        for _ in range(2):
            text = _REPETITION.sub(r"\1", text)
        text = _ORPHAN_PUNCT.sub(r"\1", text)
        text = _SPACES.sub(" ", text)
        return text.strip()
