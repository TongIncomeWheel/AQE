"""AIC voice prompts package."""

from src.aic.prompts.prompt_builder import (
    build_voice_prompt,
    build_system_blocks,
    write_compiled_prompts,
)
from src.aic.prompts.voice_config import (
    VOICES,
    DELIBERATION_ORDER,
    RISK_STRUCTURE_ORDER,
    VoiceConfig,
    get_voice,
)

__all__ = [
    "VOICES",
    "DELIBERATION_ORDER",
    "RISK_STRUCTURE_ORDER",
    "VoiceConfig",
    "get_voice",
    "build_voice_prompt",
    "build_system_blocks",
    "write_compiled_prompts",
]
