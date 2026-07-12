"""Metric types and containers for benchmark measurements."""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MetricType(str, Enum):
    """Categories of metrics collected during benchmarks."""
    REASONING = "reasoning"
    PLANNING = "planning"
    LANGUAGE = "language"
    MEMORY = "memory"
    SKILLS = "skills"
    REFLECTION = "reflection"
    LEARNING = "learning"
    EXECUTION = "execution"
    SIMULATION = "simulation"
    OVERALL = "overall"


@dataclass
class MetricValue:
    """A single named metric measurement."""
    name: str
    value: float
    metric_type: MetricType
    unit: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "value": self.value,
            "metric_type": self.metric_type.value,
            "unit": self.unit,
            "details": self.details,
        }


@dataclass
class MetricSet:
    """A collection of metric values forming a complete measurement."""
    metrics: list[MetricValue] = field(default_factory=list)
    run_id: str = ""
    timestamp: str = ""

    def add(self, name: str, value: float, metric_type: MetricType, unit: str = "", **details: Any) -> None:
        self.metrics.append(MetricValue(
            name=name, value=value, metric_type=metric_type,
            unit=unit, details=details,
        ))

    def get(self, name: str) -> float | None:
        for m in self.metrics:
            if m.name == name:
                return m.value
        return None

    def by_type(self, metric_type: MetricType) -> list[MetricValue]:
        return [m for m in self.metrics if m.metric_type == metric_type]

    def average_by_type(self, metric_type: MetricType) -> float:
        values = [m.value for m in self.by_type(metric_type)]
        return statistics.mean(values) if values else 0.0

    def overall_score(self) -> float:
        type_averages = []
        for mt in MetricType:
            if mt == MetricType.OVERALL:
                continue
            avg = self.average_by_type(mt)
            if avg > 0:
                type_averages.append(avg)
        return statistics.mean(type_averages) if type_averages else 0.0

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "metrics": [m.to_dict() for m in self.metrics],
            "overall_score": self.overall_score(),
        }
