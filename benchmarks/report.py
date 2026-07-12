"""Benchmark report generation — markdown and structured output."""

from __future__ import annotations

from dataclasses import dataclass, field
from html import escape
import statistics
from typing import Any

from .benchmark_result import BenchmarkRun


@dataclass(frozen=True)
class TrendPoint:
    run_id: str
    timestamp: str
    overall_score: float
    task_success_rate: float
    average_latency: float
    category_scores: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "overall_score": self.overall_score,
            "task_success_rate": self.task_success_rate,
            "average_latency": self.average_latency,
            "category_scores": dict(self.category_scores),
        }


@dataclass(frozen=True)
class RegressionFinding:
    scope: str
    baseline_score: float
    current_score: float
    delta: float
    threshold: float

    @property
    def severity(self) -> str:
        if self.delta <= self.threshold * 2:
            return "high"
        if self.delta <= self.threshold * 1.5:
            return "medium"
        return "low"

    def to_dict(self) -> dict[str, Any]:
        return {
            "scope": self.scope,
            "baseline_score": self.baseline_score,
            "current_score": self.current_score,
            "delta": self.delta,
            "threshold": self.threshold,
            "severity": self.severity,
        }


class BenchmarkReport:
    """Generates human-readable benchmark reports."""

    def __init__(self, run: BenchmarkRun, previous: BenchmarkRun | None = None) -> None:
        self._run = run
        self._previous = previous

    def overall_score(self) -> float:
        return self._run.overall_score

    def category_scores(self) -> dict[str, float]:
        cats: dict[str, list[float]] = {}
        for r in self._run.results:
            cats.setdefault(r.category, []).append(r.score)
        return {cat: statistics.mean(scores) for cat, scores in cats.items()}

    def strongest_area(self) -> tuple[str, float]:
        scores = self.category_scores()
        if not scores:
            return ("N/A", 0.0)
        best = max(scores, key=scores.get)
        return (best, scores[best])

    def weakest_area(self) -> tuple[str, float]:
        scores = self.category_scores()
        if not scores:
            return ("N/A", 0.0)
        worst = min(scores, key=scores.get)
        return (worst, scores[worst])

    def deltas(self) -> dict[str, float]:
        if not self._previous:
            return {}
        prev_cats: dict[str, list[float]] = {}
        for r in self._previous.results:
            prev_cats.setdefault(r.category, []).append(r.score)
        curr_cats = self.category_scores()
        prev_avgs = {cat: statistics.mean(scores) for cat, scores in prev_cats.items()}
        return {
            cat: curr_cats.get(cat, 0) - prev_avgs.get(cat, 0)
            for cat in sorted(set(list(curr_cats.keys()) + list(prev_avgs.keys())))
        }

    def trend_points(self, history: list[BenchmarkRun] | None = None) -> list[TrendPoint]:
        runs = list(history or [])
        if not runs:
            runs = [self._previous, self._run] if self._previous else [self._run]
        filtered = [run for run in runs if run is not None]
        filtered.sort(key=lambda run: run.timestamp)
        return [
            TrendPoint(
                run_id=run.run_id,
                timestamp=run.timestamp,
                overall_score=run.overall_score,
                task_success_rate=run.task_success_rate,
                average_latency=run.average_latency(),
                category_scores={
                    cat: run.category_score(cat)
                    for cat in sorted(set(result.category for result in run.results))
                },
            )
            for run in filtered
        ]

    def regression_findings(self, threshold: float = -0.05) -> list[RegressionFinding]:
        if not self._previous:
            return []
        findings: list[RegressionFinding] = []
        overall_delta = self._run.overall_score - self._previous.overall_score
        if overall_delta < threshold:
            findings.append(
                RegressionFinding(
                    "overall",
                    self._previous.overall_score,
                    self._run.overall_score,
                    overall_delta,
                    threshold,
                )
            )
        scores = self.category_scores()
        for category, delta in self.deltas().items():
            if delta < threshold:
                findings.append(
                    RegressionFinding(
                        category,
                        self._previous.category_score(category),
                        scores.get(category, 0.0),
                        delta,
                        threshold,
                    )
                )
        return findings

    def to_markdown(self) -> str:
        lines = []
        lines.append("# ARIA Benchmark Report\n")
        lines.append(f"**Run ID**: {self._run.run_id}")
        lines.append(f"**Timestamp**: {self._run.timestamp}")
        lines.append(f"**Version**: {self._run.aria_version}")
        lines.append("")
        lines.append(f"## Overall Score: {self._run.overall_score:.1f}\n")

        scores = self.category_scores()
        lines.append("| Category | Score |")
        lines.append("|----------|-------|")
        for cat in sorted(scores.keys()):
            lines.append(f"| {cat.title()} | {scores[cat]:.1f} |")
        lines.append("")

        strong_name, strong_val = self.strongest_area()
        weak_name, weak_val = self.weakest_area()
        lines.append(f"**Strongest Area**: {strong_name.title()} ({strong_val:.1f})")
        lines.append(f"**Weakest Area**: {weak_name.title()} ({weak_val:.1f})")
        lines.append("")

        lines.append(f"**Task Success Rate**: {self._run.task_success_rate:.0%}")
        lines.append(f"**Average Confidence**: {self._run.average_confidence():.2f}")
        lines.append(f"**Average Latency**: {self._run.average_latency():.1f}ms")
        lines.append(f"**Tasks**: {self._run.successful_tasks}/{self._run.total_tasks}")
        lines.append("")

        delta_vals = self.deltas()
        if delta_vals:
            lines.append("## Compared to Previous Run\n")
            lines.append("| Category | Previous | Current | Delta |")
            lines.append("|----------|----------|---------|-------|")
            for cat in sorted(delta_vals.keys()):
                d = delta_vals[cat]
                arrow = "+" if d > 0 else "" if d == 0 else ""
                prev_score = self._previous.category_score(cat) if self._previous else 0
                curr_score = scores.get(cat, 0)
                lines.append(
                    f"| {cat.title()} | {prev_score:.1f} | {curr_score:.1f} | {arrow}{d:.1f}% |"
                )
            lines.append("")

        overall_delta = self._run.overall_score - self._previous.overall_score if self._previous else 0
        if self._previous:
            lines.append(f"**Overall Change**: {'+' if overall_delta > 0 else ''}{overall_delta:.1f}%\n")

        lines.append("## Task Details\n")
        lines.append("| Task | Category | Score | Success | Duration |")
        lines.append("|------|----------|-------|---------|----------|")
        for r in self._run.results:
            status = "Yes" if r.success else "No"
            lines.append(
                f"| {r.task_name} | {r.category} | {r.score:.1f} | {status} | {r.duration_ms:.0f}ms |"
            )
        lines.append("")

        return "\n".join(lines)

    def to_html(self, *, title: str = "ARIA Benchmark Report") -> str:
        scores = self.category_scores()
        findings = self.regression_findings()
        score_rows = "\n".join(
            f"<tr><td>{escape(cat.title())}</td><td>{score:.3f}</td><td><div class=\"bar\"><i style=\"width:{max(0, min(100, score * 100)):.1f}%\"></i></div></td></tr>"
            for cat, score in sorted(scores.items())
        )
        task_rows = "\n".join(
            "<tr>"
            f"<td>{escape(r.task_name)}</td>"
            f"<td>{escape(r.category)}</td>"
            f"<td>{r.score:.3f}</td>"
            f"<td>{'pass' if r.success else 'fail'}</td>"
            f"<td>{r.duration_ms:.0f}ms</td>"
            "</tr>"
            for r in self._run.results
        )
        regression_rows = "\n".join(
            "<tr>"
            f"<td>{escape(f.scope)}</td>"
            f"<td>{f.baseline_score:.3f}</td>"
            f"<td>{f.current_score:.3f}</td>"
            f"<td>{f.delta:+.3f}</td>"
            f"<td>{escape(f.severity)}</td>"
            "</tr>"
            for f in findings
        ) or "<tr><td colspan=\"5\">No regressions detected.</td></tr>"
        trend_json = escape(str([point.to_dict() for point in self.trend_points()]))
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>
    :root {{ color-scheme: dark; --bg:#101312; --panel:#181d1b; --line:#334139; --text:#eef4ee; --muted:#9dad9f; --good:#7ad66d; --warn:#f5c84c; --bad:#ef6a5b; }}
    body {{ margin:0; background:var(--bg); color:var(--text); font-family:Inter,Segoe UI,system-ui,sans-serif; }}
    main {{ max-width:1120px; margin:0 auto; padding:28px; display:grid; gap:18px; }}
    h1,h2 {{ margin:0; }}
    .hero,.panel {{ border:1px solid var(--line); background:var(--panel); border-radius:8px; padding:18px; }}
    .hero {{ display:grid; grid-template-columns:1fr auto; gap:18px; align-items:end; }}
    .score {{ font-size:48px; font-weight:800; color:var(--good); }}
    .muted {{ color:var(--muted); }}
    .grid {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:14px; }}
    .metric {{ border:1px solid var(--line); border-radius:8px; padding:14px; background:#141a17; }}
    .metric b {{ display:block; font-size:24px; margin-top:6px; }}
    table {{ width:100%; border-collapse:collapse; font-size:14px; }}
    th,td {{ text-align:left; border-bottom:1px solid var(--line); padding:10px 8px; vertical-align:middle; }}
    th {{ color:var(--muted); font-weight:600; }}
    .bar {{ height:8px; background:#263129; border-radius:999px; overflow:hidden; }}
    .bar i {{ display:block; height:100%; background:linear-gradient(90deg,var(--good),var(--warn)); }}
    .trend {{ font-family:ui-monospace,SFMono-Regular,Consolas,monospace; font-size:12px; color:var(--muted); white-space:pre-wrap; }}
    @media (max-width:800px) {{ .hero,.grid {{ grid-template-columns:1fr; }} main {{ padding:16px; }} }}
  </style>
</head>
<body>
<main>
  <section class="hero">
    <div>
      <h1>{escape(title)}</h1>
      <p class="muted">Run {escape(self._run.run_id)} · {escape(self._run.timestamp)} · ARIA {escape(self._run.aria_version)}</p>
    </div>
    <div class="score">{self._run.overall_score:.3f}</div>
  </section>
  <section class="grid">
    <div class="metric"><span class="muted">Task Success</span><b>{self._run.task_success_rate:.0%}</b></div>
    <div class="metric"><span class="muted">Average Confidence</span><b>{self._run.average_confidence():.2f}</b></div>
    <div class="metric"><span class="muted">Average Latency</span><b>{self._run.average_latency():.0f}ms</b></div>
  </section>
  <section class="panel"><h2>Category Scores</h2><table><thead><tr><th>Category</th><th>Score</th><th>Graph</th></tr></thead><tbody>{score_rows}</tbody></table></section>
  <section class="panel"><h2>Regression Summary</h2><table><thead><tr><th>Scope</th><th>Baseline</th><th>Current</th><th>Delta</th><th>Severity</th></tr></thead><tbody>{regression_rows}</tbody></table></section>
  <section class="panel"><h2>Task Details</h2><table><thead><tr><th>Task</th><th>Category</th><th>Score</th><th>Status</th><th>Duration</th></tr></thead><tbody>{task_rows}</tbody></table></section>
  <section class="panel"><h2>Trend Data</h2><div class="trend">{trend_json}</div></section>
</main>
</body>
</html>"""

    def to_dict(self) -> dict:
        result = {
            "run_id": self._run.run_id,
            "timestamp": self._run.timestamp,
            "aria_version": self._run.aria_version,
            "overall_score": self._run.overall_score,
            "category_scores": self.category_scores(),
            "strongest_area": self.strongest_area(),
            "weakest_area": self.weakest_area(),
            "task_success_rate": self._run.task_success_rate,
            "average_confidence": self._run.average_confidence(),
            "average_latency": self._run.average_latency(),
            "total_tasks": self._run.total_tasks,
            "successful_tasks": self._run.successful_tasks,
            "results": [r.to_dict() for r in self._run.results],
        }
        if self._previous:
            result["previous_run_id"] = self._previous.run_id
            result["deltas"] = self.deltas()
            result["regressions"] = [finding.to_dict() for finding in self.regression_findings()]
        result["trend_points"] = [point.to_dict() for point in self.trend_points()]
        return result

    def summary(self) -> str:
        strong_name, strong_val = self.strongest_area()
        weak_name, weak_val = self.weakest_area()
        delta_str = ""
        if self._previous:
            overall_delta = self._run.overall_score - self._previous.overall_score
            delta_str = f" (change: {'+' if overall_delta > 0 else ''}{overall_delta:.1f}%)"
        return (
            f"ARIA Benchmark Report — {self._run.run_id}\n"
            f"Overall Score: {self._run.overall_score:.1f}{delta_str}\n"
            f"Strongest: {strong_name.title()} ({strong_val:.1f}) | "
            f"Weakest: {weak_name.title()} ({weak_val:.1f})\n"
            f"Tasks: {self._run.successful_tasks}/{self._run.total_tasks} passed "
            f"({self._run.task_success_rate:.0%})"
        )
