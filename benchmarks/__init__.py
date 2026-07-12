"""ARIA Benchmark & Evaluation Framework.

Provides objective measurement of ARIA's cognitive performance over time.
"""

import sys
from pathlib import Path

# Ensure project root is on sys.path for benchmark task imports
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from .metrics import MetricType, MetricValue, MetricSet
from .benchmark_result import BenchmarkResult, BenchmarkRun
from .benchmark_registry import BenchmarkRegistry
from .benchmark_suite import BenchmarkSuite, SuiteResult
from .benchmark_runner import BenchmarkRunner
from .report import BenchmarkReport

__all__ = [
    "MetricType", "MetricValue", "MetricSet",
    "BenchmarkResult", "BenchmarkRun",
    "BenchmarkRegistry",
    "BenchmarkSuite", "SuiteResult",
    "BenchmarkRunner",
    "BenchmarkReport",
]
