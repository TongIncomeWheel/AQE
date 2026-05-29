"""Filter recipe schema + persistence + apply-to-DataFrame."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd


from src.data.paths import OUTPUT_DIR, PROJECT_ROOT

RECIPES_FILE = OUTPUT_DIR / "recipes.json"


@dataclass
class Recipe:
    name: str = "Default"
    sc_mom_min: float = 75.0
    flow_min: float = 0.0
    energy_min: float = 0.0
    structure_min: float = 0.0
    mp_min: float = 0.0
    mp_states: list[str] = field(default_factory=lambda: ["BUILDING", "STRONG", "FADING"])
    elder_min: float = 0.0
    cooldown_days: int = 21

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Recipe":
        known = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in payload.items() if k in known})


def load_recipes() -> list[Recipe]:
    if not RECIPES_FILE.exists():
        return []
    try:
        payload = json.loads(RECIPES_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return [Recipe.from_dict(item) for item in payload]


def save_recipes(recipes: list[Recipe]) -> None:
    RECIPES_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = [r.to_dict() for r in recipes]
    RECIPES_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def upsert_recipe(recipes: list[Recipe], recipe: Recipe) -> list[Recipe]:
    """Replace by name if present, else append."""
    out = [r for r in recipes if r.name != recipe.name]
    out.append(recipe)
    return out


def apply_filter(signals_with_context: pd.DataFrame, recipe: Recipe) -> pd.DataFrame:
    """Filter the signals frame down to rows matching the recipe.

    Note: `cooldown_days` is enforced at signal-detection time (see signal_detector),
    NOT here. Applying it again here would double-count.
    """
    if signals_with_context.empty:
        return signals_with_context.copy()
    df = signals_with_context
    mask = (
        (df["sc_momentum"] >= recipe.sc_mom_min)
        & (df["flow_100"] >= recipe.flow_min)
        & (df["energy_100"] >= recipe.energy_min)
        & (df["structure_100"] >= recipe.structure_min)
        & (df["mp_100"] >= recipe.mp_min)
        & (df["elder_score"] >= recipe.elder_min)
        & (df["mp_state"].isin(recipe.mp_states))
    )
    return df.loc[mask].reset_index(drop=True)
