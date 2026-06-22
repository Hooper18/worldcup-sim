"""模型束：DC-on-Elo + 纯攻防 + 融合权重 + 回测摘要，统一持久化到 params.json。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .dc_attack import DcAttackParams
from .dc_elo import DcEloParams
from .score_model import DcAttackModel, DcEloModel, EnsembleModel


@dataclass
class ModelBundle:
    dc_elo: DcEloParams
    dc_attack: DcAttackParams  # att/def 已按队伍代码键重映射（仅 48 队）
    weight_dc_elo: float
    half_life_days: float
    backtest: dict = field(default_factory=dict)
    diagnostics: dict = field(default_factory=dict)  # CV 选定的 ridge、经验主场优势等

    @property
    def weight_dc_attack(self) -> float:
        return 1.0 - self.weight_dc_elo

    def to_dict(self) -> dict:
        return {
            "dc_elo": self.dc_elo.to_dict(),
            "dc_attack": self.dc_attack.to_dict(),
            "weight_dc_elo": self.weight_dc_elo,
            "half_life_days": self.half_life_days,
            "backtest": self.backtest,
            "diagnostics": self.diagnostics,
        }

    @classmethod
    def from_dict(cls, d: dict) -> ModelBundle:
        return cls(
            dc_elo=DcEloParams.from_dict(d["dc_elo"]),
            dc_attack=DcAttackParams.from_dict(d["dc_attack"]),
            weight_dc_elo=d["weight_dc_elo"],
            half_life_days=d["half_life_days"],
            backtest=d.get("backtest", {}),
            diagnostics=d.get("diagnostics", {}),
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )

    @classmethod
    def load(cls, path: Path) -> ModelBundle:
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def build_model(self, elo_by_code: dict[str, float]) -> EnsembleModel:
        return EnsembleModel(
            [
                (DcEloModel(self.dc_elo, elo_by_code), self.weight_dc_elo),
                (DcAttackModel(self.dc_attack), self.weight_dc_attack),
            ]
        )
