"""Comprehensive tests for the ARIA Benchmark Framework."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

import pytest

# Ensure project root is on sys.path for imports
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from benchmarks.metrics import MetricType, MetricValue, MetricSet
from benchmarks.benchmark_result import BenchmarkResult, BenchmarkRun, BenchmarkHistory
from benchmarks.benchmark_registry import BenchmarkRegistry, get_registry, register_default_tasks
from benchmarks.benchmark_suite import BenchmarkSuite, SuiteResult
from benchmarks.benchmark_runner import BenchmarkRunner
from benchmarks.report import BenchmarkReport

from aria_core.integration import ARIACore


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def fresh_registry():
    return BenchmarkRegistry()


@pytest.fixture
def sample_result():
    return BenchmarkResult(
        task_name="test_task",
        category="reasoning",
        success=True,
        score=0.85,
        duration_ms=120.0,
        confidence=0.9,
    )


@pytest.fixture
def sample_run(sample_result):
    from benchmarks.metrics import MetricSet, MetricType
    metrics = MetricSet(run_id="test_run_1", timestamp="2025-01-01T00:00:00")
    metrics.add("reasoning_score", 0.85, MetricType.REASONING)
    metrics.add("task_success_rate", 1.0, MetricType.OVERALL)
    return BenchmarkRun(
        run_id="test_run_1",
        timestamp="2025-01-01T00:00:00",
        aria_version="1.0.0",
        results=[sample_result],
        metrics=metrics,
    )


@pytest.fixture
def aria_instance():
    """Create a real ARIACore instance for integration tests."""
    core = ARIACore()
    yield core
    core.shutdown()


# ---------------------------------------------------------------------------
# MetricType tests
# ---------------------------------------------------------------------------

class TestMetricType:
    def test_all_types_exist(self):
        types = [t.value for t in MetricType]
        expected = ["reasoning", "planning", "language", "memory",
                    "skills", "reflection", "learning", "execution", "overall"]
        for e in expected:
            assert e in types

    def test_metric_type_is_string_enum(self):
        assert MetricType.REASONING.value == "reasoning"
        assert str(MetricType.PLANNING) == "MetricType.PLANNING"


# ---------------------------------------------------------------------------
# MetricValue tests
# ---------------------------------------------------------------------------

class TestMetricValue:
    def test_creation(self):
        mv = MetricValue(name="test", value=0.85, metric_type=MetricType.REASONING)
        assert mv.name == "test"
        assert mv.value == 0.85
        assert mv.metric_type == MetricType.REASONING

    def test_to_dict(self):
        mv = MetricValue(name="test", value=0.85, metric_type=MetricType.REASONING, unit="%")
        d = mv.to_dict()
        assert d["name"] == "test"
        assert d["value"] == 0.85
        assert d["metric_type"] == "reasoning"
        assert d["unit"] == "%"


# ---------------------------------------------------------------------------
# MetricSet tests
# ---------------------------------------------------------------------------

class TestMetricSet:
    def test_add_and_get(self):
        ms = MetricSet()
        ms.add("score", 0.9, MetricType.REASONING)
        assert ms.get("score") == 0.9

    def test_get_missing(self):
        ms = MetricSet()
        assert ms.get("missing") is None

    def test_by_type(self):
        ms = MetricSet()
        ms.add("r1", 0.8, MetricType.REASONING)
        ms.add("r2", 0.9, MetricType.REASONING)
        ms.add("p1", 0.7, MetricType.PLANNING)
        reasoning = ms.by_type(MetricType.REASONING)
        assert len(reasoning) == 2

    def test_average_by_type(self):
        ms = MetricSet()
        ms.add("r1", 0.8, MetricType.REASONING)
        ms.add("r2", 0.6, MetricType.REASONING)
        assert ms.average_by_type(MetricType.REASONING) == 0.7

    def test_average_by_type_empty(self):
        ms = MetricSet()
        assert ms.average_by_type(MetricType.REASONING) == 0.0

    def test_overall_score(self):
        ms = MetricSet()
        ms.add("r1", 0.8, MetricType.REASONING)
        ms.add("p1", 0.6, MetricType.PLANNING)
        overall = ms.overall_score()
        assert 0 < overall <= 1.0

    def test_to_dict(self):
        ms = MetricSet(run_id="r1", timestamp="2025-01-01")
        ms.add("score", 0.9, MetricType.REASONING)
        d = ms.to_dict()
        assert d["run_id"] == "r1"
        assert len(d["metrics"]) == 1
        assert "overall_score" in d


# ---------------------------------------------------------------------------
# BenchmarkResult tests
# ---------------------------------------------------------------------------

class TestBenchmarkResult:
    def test_creation(self, sample_result):
        assert sample_result.task_name == "test_task"
        assert sample_result.success is True
        assert sample_result.score == 0.85

    def test_to_dict(self, sample_result):
        d = sample_result.to_dict()
        assert d["task_name"] == "test_task"
        assert d["category"] == "reasoning"
        assert d["success"] is True

    def test_failed_result(self):
        r = BenchmarkResult(
            task_name="fail", category="skills", success=False, score=0.0,
            errors=["something went wrong"],
        )
        assert not r.success
        assert len(r.errors) == 1


# ---------------------------------------------------------------------------
# BenchmarkRun tests
# ---------------------------------------------------------------------------

class TestBenchmarkRun:
    def test_overall_score(self, sample_run):
        assert sample_run.overall_score > 0

    def test_task_success_rate(self, sample_run):
        assert sample_run.task_success_rate == 1.0

    def test_category_score(self, sample_run):
        score = sample_run.category_score("reasoning")
        assert score == 0.85

    def test_category_score_missing(self, sample_run):
        assert sample_run.category_score("nonexistent") == 0.0

    def test_average_confidence(self, sample_run):
        assert sample_run.average_confidence() == 0.9

    def test_average_latency(self, sample_run):
        assert sample_run.average_latency() == 120.0

    def test_to_dict(self, sample_run):
        d = sample_run.to_dict()
        assert d["run_id"] == "test_run_1"
        assert "overall_score" in d
        assert "category_scores" in d

    def test_multiple_results(self):
        results = [
            BenchmarkResult(task_name="t1", category="reasoning", success=True, score=0.8),
            BenchmarkResult(task_name="t2", category="planning", success=True, score=0.9),
            BenchmarkResult(task_name="t3", category="reasoning", success=False, score=0.3),
        ]
        run = BenchmarkRun(results=results)
        assert run.total_tasks == 3
        assert run.successful_tasks == 2
        assert run.task_success_rate == pytest.approx(2 / 3)


# ---------------------------------------------------------------------------
# BenchmarkHistory tests
# ---------------------------------------------------------------------------

class TestBenchmarkHistory:
    def test_save_and_load(self, sample_run):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            history = BenchmarkHistory(db_path=db_path)
            history.save_run(sample_run)
            loaded = history.load_run("test_run_1")
            assert loaded is not None
            assert loaded.run_id == "test_run_1"
            assert loaded.overall_score > 0
            history.close()
        finally:
            os.unlink(db_path)

    def test_latest_run(self, sample_run):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            history = BenchmarkHistory(db_path=db_path)
            history.save_run(sample_run)
            latest = history.latest_run()
            assert latest is not None
            assert latest.run_id == "test_run_1"
            history.close()
        finally:
            os.unlink(db_path)

    def test_best_run(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            history = BenchmarkHistory(db_path=db_path)
            run1 = BenchmarkRun(
                run_id="r1", timestamp="2025-01-01",
                results=[BenchmarkResult(task_name="t1", category="reasoning", success=True, score=0.6)],
            )
            run2 = BenchmarkRun(
                run_id="r2", timestamp="2025-01-02",
                results=[BenchmarkResult(task_name="t1", category="reasoning", success=True, score=0.9)],
            )
            history.save_run(run1)
            history.save_run(run2)
            best = history.best_run()
            assert best is not None
            assert best.run_id == "r2"
            history.close()
        finally:
            os.unlink(db_path)

    def test_all_runs(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            history = BenchmarkHistory(db_path=db_path)
            for i in range(5):
                run = BenchmarkRun(
                    run_id=f"run_{i}", timestamp=f"2025-01-0{i+1}",
                    results=[BenchmarkResult(task_name="t", category="reasoning", success=True, score=0.5 + i * 0.1)],
                )
                history.save_run(run)
            runs = history.all_runs(limit=3)
            assert len(runs) == 3
            history.close()
        finally:
            os.unlink(db_path)

    def test_compare_runs(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            history = BenchmarkHistory(db_path=db_path)
            run_a = BenchmarkRun(
                run_id="a", timestamp="2025-01-01",
                results=[
                    BenchmarkResult(task_name="t1", category="reasoning", success=True, score=0.5),
                    BenchmarkResult(task_name="t2", category="planning", success=True, score=0.6),
                ],
            )
            run_b = BenchmarkRun(
                run_id="b", timestamp="2025-01-02",
                results=[
                    BenchmarkResult(task_name="t1", category="reasoning", success=True, score=0.8),
                    BenchmarkResult(task_name="t2", category="planning", success=True, score=0.7),
                ],
            )
            history.save_run(run_a)
            history.save_run(run_b)
            comparison = history.compare_runs("a", "b")
            assert comparison["overall_delta"] > 0
            assert comparison["category_comparisons"]["reasoning"]["improved"]
            history.close()
        finally:
            os.unlink(db_path)

    def test_performance_trend(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            history = BenchmarkHistory(db_path=db_path)
            for i in range(5):
                run = BenchmarkRun(
                    run_id=f"r{i}", timestamp=f"2025-01-0{i+1}",
                    results=[BenchmarkResult(task_name="t", category="reasoning", success=True, score=0.5 + i * 0.1)],
                )
                history.save_run(run)
            trend = history.performance_trend(last_n=3)
            assert len(trend) == 3
            assert trend[0]["overall_score"] >= trend[-1]["overall_score"]
            history.close()
        finally:
            os.unlink(db_path)

    def test_regression_report(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            history = BenchmarkHistory(db_path=db_path)
            run_a = BenchmarkRun(
                run_id="a", timestamp="2025-01-01",
                results=[BenchmarkResult(task_name="t", category="reasoning", success=True, score=0.9)],
            )
            run_b = BenchmarkRun(
                run_id="b", timestamp="2025-01-02",
                results=[BenchmarkResult(task_name="t", category="reasoning", success=True, score=0.5)],
            )
            history.save_run(run_a)
            history.save_run(run_b)
            report = history.regression_report(baseline_id="a", threshold=-0.1)
            assert report["status"] == "ok"
            assert report["has_regression"]
            history.close()
        finally:
            os.unlink(db_path)

    def test_export_json(self, sample_run):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            history = BenchmarkHistory(db_path=db_path)
            history.save_run(sample_run)
            json_path = db_path + ".json"
            history.export_json(json_path)
            with open(json_path) as f:
                data = json.load(f)
            assert len(data) == 1
            assert data[0]["run_id"] == "test_run_1"
            os.unlink(json_path)
            history.close()
        finally:
            os.unlink(db_path)

    def test_export_markdown(self, sample_run):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            history = BenchmarkHistory(db_path=db_path)
            history.save_run(sample_run)
            md_path = db_path + ".md"
            history.export_markdown(md_path)
            with open(md_path) as f:
                content = f.read()
            assert "ARIA Benchmark History" in content
            assert "test_run_1" in content
            os.unlink(md_path)
            history.close()
        finally:
            os.unlink(db_path)


# ---------------------------------------------------------------------------
# BenchmarkRegistry tests
# ---------------------------------------------------------------------------

class TestBenchmarkRegistry:
    def test_register_task(self, fresh_registry):
        def dummy(aria, **kwargs):
            return BenchmarkResult(task_name="dummy", category="test", success=True, score=1.0)
        fresh_registry.register_task("dummy", "test", "A dummy task", dummy)
        assert fresh_registry.count() == 1
        task = fresh_registry.get_task("dummy")
        assert task is not None
        assert task.category == "test"

    def test_register_suite(self, fresh_registry):
        def t1(aria, **kwargs): return 1.0
        def t2(aria, **kwargs): return 1.0
        fresh_registry.register_task("t1", "cat", "Task 1", t1)
        fresh_registry.register_task("t2", "cat", "Task 2", t2)
        fresh_registry.register_suite("test_suite", ["t1", "t2"])
        assert "test_suite" in fresh_registry.list_suites()

    def test_list_tasks_by_category(self, fresh_registry):
        def t1(aria, **kwargs): return 1.0
        def t2(aria, **kwargs): return 1.0
        fresh_registry.register_task("t1", "cat_a", "Task 1", t1)
        fresh_registry.register_task("t2", "cat_b", "Task 2", t2)
        cat_a = fresh_registry.list_tasks(category="cat_a")
        assert len(cat_a) == 1
        assert cat_a[0].name == "t1"

    def test_list_categories(self, fresh_registry):
        def t1(aria, **kwargs): return 1.0
        def t2(aria, **kwargs): return 1.0
        fresh_registry.register_task("t1", "cat_a", "Task 1", t1)
        fresh_registry.register_task("t2", "cat_b", "Task 2", t2)
        cats = fresh_registry.list_categories()
        assert "cat_a" in cats
        assert "cat_b" in cats

    def test_register_default_tasks(self):
        registry = register_default_tasks()
        assert registry.count() > 0
        cats = registry.list_categories()
        assert "reasoning" in cats
        assert "planning" in cats
        assert "language" in cats
        assert "memory" in cats
        assert "skills" in cats
        assert "execution" in cats
        assert "learning" in cats
        assert "reflection" in cats

    def test_default_suites_registered(self):
        registry = register_default_tasks()
        suites = registry.list_suites()
        assert "reasoning" in suites
        assert "planning" in suites
        assert "language" in suites
        assert "memory" in suites
        assert "skills" in suites
        assert "execution" in suites
        assert "learning" in suites
        assert "reflection" in suites


# ---------------------------------------------------------------------------
# BenchmarkSuite tests
# ---------------------------------------------------------------------------

class TestBenchmarkSuite:
    def test_run_empty_suite(self, fresh_registry):
        suite = BenchmarkSuite(fresh_registry)
        result = suite.run_suite("nonexistent", None)
        assert result.total_count == 0

    def test_run_suite_with_tasks(self, fresh_registry, aria_instance):
        def passing(aria, **kwargs):
            return BenchmarkResult(task_name="pass", category="test", success=True, score=1.0)
        fresh_registry.register_task("pass_task", "test", "Passing task", passing)
        fresh_registry.register_suite("test_suite", ["pass_task"])

        suite = BenchmarkSuite(fresh_registry)
        result = suite.run_suite("test_suite", aria_instance)
        assert result.total_count == 1
        assert result.success_count == 1
        assert result.average_score == 1.0

    def test_run_suite_with_failing_task(self, fresh_registry, aria_instance):
        def failing(aria, **kwargs):
            raise ValueError("intentional failure")
        fresh_registry.register_task("fail_task", "test", "Failing task", failing)
        fresh_registry.register_suite("fail_suite", ["fail_task"])

        suite = BenchmarkSuite(fresh_registry)
        result = suite.run_suite("fail_suite", aria_instance)
        assert result.total_count == 1
        assert result.success_count == 0

    def test_run_all_suites(self, fresh_registry, aria_instance):
        def t1(aria, **kwargs):
            return BenchmarkResult(task_name="t1", category="cat1", success=True, score=1.0)
        def t2(aria, **kwargs):
            return BenchmarkResult(task_name="t2", category="cat2", success=True, score=0.9)
        fresh_registry.register_task("t1", "cat1", "Task 1", t1)
        fresh_registry.register_task("t2", "cat2", "Task 2", t2)
        fresh_registry.register_suite("suite1", ["t1"])
        fresh_registry.register_suite("suite2", ["t2"])

        suite = BenchmarkSuite(fresh_registry)
        results = suite.run_all(aria_instance)
        assert "suite1" in results
        assert "suite2" in results
        assert results["suite1"].average_score == 1.0


# ---------------------------------------------------------------------------
# BenchmarkRunner tests
# ---------------------------------------------------------------------------

class TestBenchmarkRunner:
    def test_run_all_benchmarks(self, aria_instance):
        runner = BenchmarkRunner()
        run = runner.run(aria_instance, version="test")
        assert run.overall_score > 0
        assert run.total_tasks > 0
        assert run.run_id.startswith("run_")

    def test_run_specific_suite(self, aria_instance):
        runner = BenchmarkRunner()
        run = runner.run(aria_instance, suite="reasoning", version="test")
        assert run.total_tasks > 0
        for r in run.results:
            assert r.category == "reasoning"

    def test_latest_run(self, aria_instance):
        runner = BenchmarkRunner()
        runner.run(aria_instance, version="test")
        latest = runner.latest_run()
        assert latest is not None
        assert latest.run_id.startswith("run_")

    def test_compare_runs(self, aria_instance):
        runner = BenchmarkRunner()
        run1 = runner.run(aria_instance, suite="reasoning", version="test")
        run2 = runner.run(aria_instance, suite="reasoning", version="test")
        comparison = runner.compare(run1.run_id, run2.run_id)
        assert "overall_delta" in comparison
        assert "category_comparisons" in comparison

    def test_trend(self, aria_instance):
        runner = BenchmarkRunner()
        runner.run(aria_instance, suite="reasoning", version="test")
        runner.run(aria_instance, suite="reasoning", version="test")
        trend = runner.trend(last_n=2)
        assert len(trend) == 2

    def test_report(self, aria_instance):
        runner = BenchmarkRunner()
        run = runner.run(aria_instance, version="test")
        report = runner.report(run)
        md = report.to_markdown()
        assert "ARIA Benchmark Report" in md
        assert "Overall Score" in md

    def test_export_json(self, aria_instance):
        runner = BenchmarkRunner()
        runner.run(aria_instance, suite="reasoning", version="test")
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            json_path = f.name
        try:
            runner.export_json(json_path)
            with open(json_path) as f:
                data = json.load(f)
            assert len(data) > 0
        finally:
            os.unlink(json_path)

    def test_export_markdown(self, aria_instance):
        runner = BenchmarkRunner()
        runner.run(aria_instance, suite="reasoning", version="test")
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as f:
            md_path = f.name
        try:
            runner.export_markdown(md_path)
            with open(md_path) as f:
                content = f.read()
            assert "ARIA Benchmark History" in content
        finally:
            os.unlink(md_path)


# ---------------------------------------------------------------------------
# BenchmarkReport tests
# ---------------------------------------------------------------------------

class TestBenchmarkReport:
    def test_overall_score(self, sample_run):
        report = BenchmarkReport(sample_run)
        assert report.overall_score() > 0

    def test_category_scores(self, sample_run):
        report = BenchmarkReport(sample_run)
        scores = report.category_scores()
        assert "reasoning" in scores

    def test_strongest_area(self, sample_run):
        report = BenchmarkReport(sample_run)
        name, val = report.strongest_area()
        assert name == "reasoning"
        assert val == 0.85

    def test_weakest_area(self, sample_run):
        report = BenchmarkReport(sample_run)
        name, val = report.weakest_area()
        assert val <= 1.0

    def test_deltas_without_previous(self, sample_run):
        report = BenchmarkReport(sample_run)
        assert report.deltas() == {}

    def test_deltas_with_previous(self, sample_run):
        prev = BenchmarkRun(
            run_id="prev", timestamp="2024-01-01",
            results=[BenchmarkResult(task_name="test_task", category="reasoning", success=True, score=0.7)],
        )
        report = BenchmarkReport(sample_run, previous=prev)
        deltas = report.deltas()
        assert "reasoning" in deltas
        assert deltas["reasoning"] > 0

    def test_to_markdown(self, sample_run):
        report = BenchmarkReport(sample_run)
        md = report.to_markdown()
        assert "ARIA Benchmark Report" in md
        assert "Overall Score" in md
        assert "reasoning" in md.lower()

    def test_to_html(self, sample_run):
        report = BenchmarkReport(sample_run)
        html = report.to_html()

        assert "<!doctype html>" in html
        assert "ARIA Benchmark Report" in html
        assert "Category Scores" in html
        assert "Regression Summary" in html
        assert "Trend Data" in html

    def test_regression_findings(self, sample_run):
        prev = BenchmarkRun(
            run_id="prev",
            timestamp="2024-01-01",
            results=[BenchmarkResult(task_name="test_task", category="reasoning", success=True, score=0.95)],
        )
        report = BenchmarkReport(sample_run, previous=prev)

        findings = report.regression_findings(threshold=-0.05)

        assert findings
        assert findings[0].scope in {"overall", "reasoning"}
        assert findings[0].to_dict()["severity"] in {"low", "medium", "high"}

    def test_trend_points(self, sample_run):
        prev = BenchmarkRun(
            run_id="prev",
            timestamp="2024-01-01",
            results=[BenchmarkResult(task_name="test_task", category="reasoning", success=True, score=0.7)],
        )
        report = BenchmarkReport(sample_run, previous=prev)

        trend = report.trend_points()

        assert [point.run_id for point in trend] == ["prev", "test_run_1"]
        assert trend[-1].to_dict()["category_scores"]["reasoning"] == 0.85

    def test_to_dict(self, sample_run):
        report = BenchmarkReport(sample_run)
        d = report.to_dict()
        assert "run_id" in d
        assert "overall_score" in d
        assert "category_scores" in d
        assert "trend_points" in d

    def test_summary(self, sample_run):
        report = BenchmarkReport(sample_run)
        s = report.summary()
        assert "test_run_1" in s
        assert "Overall Score" in s


# ---------------------------------------------------------------------------
# Integration: full pipeline
# ---------------------------------------------------------------------------

class TestBenchmarkIntegration:
    def test_full_benchmark_pipeline(self, aria_instance):
        """Test the complete benchmark pipeline: run -> persist -> report -> compare."""
        runner = BenchmarkRunner()

        run1 = runner.run(aria_instance, suite="reasoning", version="test_v1")
        assert run1.overall_score >= 0

        run2 = runner.run(aria_instance, suite="reasoning", version="test_v1")
        assert run2.overall_score >= 0

        comparison = runner.compare(run1.run_id, run2.run_id)
        assert "overall_delta" in comparison

        report = runner.report(run2)
        md = report.to_markdown()
        assert len(md) > 0

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            json_path = f.name
        try:
            runner.export_json(json_path)
            with open(json_path) as f:
                data = json.load(f)
            assert len(data) >= 2
        finally:
            os.unlink(json_path)

    def test_all_suites_run(self, aria_instance):
        """Test that all default suites execute without error."""
        runner = BenchmarkRunner()
        run = runner.run(aria_instance, version="test")
        assert run.total_tasks > 0
        categories = set(r.category for r in run.results)
        expected = {"reasoning", "planning", "language", "memory", "skills", "execution", "learning", "reflection"}
        assert categories == expected

    def test_metrics_computed(self, aria_instance):
        """Test that metrics are properly computed from results."""
        runner = BenchmarkRunner()
        run = runner.run(aria_instance, suite="reasoning", version="test")
        assert run.metrics.get("task_success_rate") is not None
        assert run.metrics.get("average_confidence") is not None
        assert run.metrics.get("reasoning_score") is not None


# ---------------------------------------------------------------------------
# Regression detection
# ---------------------------------------------------------------------------

class TestRegressionDetection:
    def test_no_regression_with_identical_runs(self, aria_instance):
        runner = BenchmarkRunner()
        run1 = runner.run(aria_instance, suite="reasoning", version="test")
        run2 = runner.run(aria_instance, suite="reasoning", version="test")
        reg = runner.regression(baseline_id=run1.run_id, threshold=-10.0)
        # With identical runs, no regression should be detected at -10% threshold
        if reg.get("status") == "ok":
            assert not reg.get("has_regression", True)

    def test_regression_with_degraded_run(self):
        """Test regression detection with intentionally degraded scores."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            history = BenchmarkHistory(db_path=db_path)
            good_run = BenchmarkRun(
                run_id="good", timestamp="2025-01-01",
                results=[
                    BenchmarkResult(task_name="t", category="reasoning", success=True, score=0.9),
                ],
            )
            bad_run = BenchmarkRun(
                run_id="bad", timestamp="2025-01-02",
                results=[
                    BenchmarkResult(task_name="t", category="reasoning", success=True, score=0.3),
                ],
            )
            history.save_run(good_run)
            history.save_run(bad_run)
            reg = history.regression_report(baseline_id="good", threshold=-0.1)
            assert reg["status"] == "ok"
            assert reg["has_regression"]
            history.close()
        finally:
            os.unlink(db_path)
