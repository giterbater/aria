"""Static HTML dashboard for ARIA World simulation results."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class DashboardRenderer:
    """Render an interactive, dependency-free dashboard from simulation data."""

    def __init__(self, result: dict[str, Any], benchmark: dict[str, Any] | None = None) -> None:
        self.result = result
        self.benchmark = benchmark or {}

    def write(self, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self.render_html(), encoding="utf-8")
        return target

    def render_html(self) -> str:
        payload = json.dumps(self._payload(), default=str)
        return DASHBOARD_HTML.replace("__ARIA_WORLD_DATA__", payload)

    def _payload(self) -> dict[str, Any]:
        result = self.benchmark.get("simulation_result") or self.result
        benchmark = self._benchmark_payload(self.benchmark)
        return {
            "result": result,
            "benchmark": benchmark,
            "summary": {
                "days": result.get("days_run", 0),
                "initialPopulation": result.get("initial_population", 0),
                "finalPopulation": result.get("final_population", 0),
                "survivalRate": result.get("survival_rate", 0),
                "happiness": result.get("average_happiness", 0),
                "knowledge": result.get("average_knowledge", 0),
                "trades": result.get("total_trades", 0),
                "conflicts": result.get("total_conflicts", 0),
                "births": result.get("total_births", 0),
            },
        }

    @staticmethod
    def _benchmark_payload(benchmark: dict[str, Any]) -> dict[str, Any]:
        if not benchmark:
            return {"metrics": [], "overallScore": 0}
        metric_set = benchmark.get("metric_set")
        if hasattr(metric_set, "to_dict"):
            metrics = metric_set.to_dict()
        elif isinstance(metric_set, dict):
            metrics = metric_set
        else:
            metrics = {"metrics": [], "overall_score": 0}
        results = [
            item.to_dict() if hasattr(item, "to_dict") else item
            for item in benchmark.get("benchmark_results", [])
        ]
        return {
            "metrics": metrics.get("metrics", []),
            "overallScore": metrics.get("overall_score", 0),
            "results": results,
        }


def render_dashboard(result: dict[str, Any], benchmark: dict[str, Any] | None = None) -> str:
    return DashboardRenderer(result, benchmark).render_html()


def write_dashboard(result: dict[str, Any], path: str | Path, benchmark: dict[str, Any] | None = None) -> Path:
    return DashboardRenderer(result, benchmark).write(path)


DASHBOARD_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ARIA World Dashboard</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #101312;
      --panel: #181d1b;
      --panel-2: #202722;
      --line: #344039;
      --text: #eef4ee;
      --muted: #9dad9f;
      --green: #7ad66d;
      --gold: #f5c84c;
      --red: #ef6a5b;
      --blue: #6bb7ff;
      --violet: #b890ff;
      --cyan: #65d6cf;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      letter-spacing: 0;
    }
    header {
      display: flex;
      align-items: end;
      justify-content: space-between;
      gap: 24px;
      padding: 24px 28px 16px;
      border-bottom: 1px solid var(--line);
      background: #151917;
    }
    h1 { margin: 0; font-size: 28px; line-height: 1.05; }
    .sub { color: var(--muted); margin-top: 6px; font-size: 14px; }
    .badge {
      border: 1px solid var(--line);
      padding: 8px 10px;
      border-radius: 6px;
      color: var(--muted);
      white-space: nowrap;
      font-size: 13px;
    }
    main { padding: 18px; display: grid; gap: 16px; }
    .metrics {
      display: grid;
      grid-template-columns: repeat(6, minmax(120px, 1fr));
      gap: 12px;
    }
    .card, .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
    }
    .card { padding: 14px; min-height: 84px; }
    .label { color: var(--muted); font-size: 12px; text-transform: uppercase; }
    .value { margin-top: 8px; font-size: 25px; font-weight: 700; }
    .grid {
      display: grid;
      grid-template-columns: minmax(420px, 1.4fr) minmax(320px, 1fr);
      gap: 16px;
      align-items: stretch;
    }
    .panel h2 {
      margin: 0;
      padding: 14px 16px;
      font-size: 16px;
      border-bottom: 1px solid var(--line);
      background: var(--panel-2);
    }
    .panel-body { padding: 14px 16px 16px; }
    canvas { display: block; width: 100%; height: 420px; background: #111b1b; }
    svg { width: 100%; min-height: 300px; display: block; }
    .map-wrap { position: relative; }
    .hud {
      position: absolute;
      left: 14px;
      top: 14px;
      display: flex;
      gap: 8px;
      align-items: center;
      padding: 8px;
      border: 1px solid rgba(238,244,238,.16);
      border-radius: 8px;
      background: rgba(16,19,18,.78);
      backdrop-filter: blur(8px);
    }
    button {
      border: 1px solid var(--line);
      background: #202722;
      color: var(--text);
      border-radius: 6px;
      min-width: 36px;
      height: 32px;
      cursor: pointer;
    }
    input[type="range"] { width: 170px; accent-color: var(--green); }
    .day-label { color: var(--muted); font-size: 13px; min-width: 72px; text-align: right; }
    .bars { display: grid; gap: 10px; }
    .bar-row { display: grid; grid-template-columns: 96px 1fr 56px; gap: 10px; align-items: center; font-size: 13px; }
    .bar-track { height: 10px; background: #273129; border-radius: 999px; overflow: hidden; }
    .bar-fill { height: 100%; background: var(--green); }
    .two {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 16px;
    }
    .list { display: grid; gap: 8px; margin: 0; padding: 0; list-style: none; }
    .list li { padding: 9px 10px; background: #151b18; border: 1px solid #2b342f; border-radius: 6px; }
    .agent-strip {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: 8px;
      margin-top: 12px;
    }
    .agent-pill {
      display: grid;
      grid-template-columns: 10px 1fr auto;
      align-items: center;
      gap: 8px;
      padding: 8px 10px;
      border: 1px solid #2b342f;
      border-radius: 6px;
      background: #151b18;
      color: var(--muted);
      font-size: 12px;
    }
    .agent-pill strong { color: var(--text); font-size: 13px; }
    .legend { display: flex; flex-wrap: wrap; gap: 12px; color: var(--muted); font-size: 13px; padding-top: 10px; }
    .dot { width: 10px; height: 10px; display: inline-block; border-radius: 999px; margin-right: 6px; }
    @media (max-width: 980px) {
      .metrics { grid-template-columns: repeat(2, minmax(120px, 1fr)); }
      .grid, .two { grid-template-columns: 1fr; }
      header { display: block; }
      .badge { display: inline-block; margin-top: 12px; }
    }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>ARIA World Dashboard</h1>
      <div class="sub">Snapshot view of ARIA simulation agents, trust, knowledge, resources, culture, innovation, and benchmark health.</div>
    </div>
    <div class="badge" id="runBadge">loading</div>
  </header>
  <main>
    <section class="metrics" id="metrics"></section>
    <section class="grid">
      <article class="panel">
        <h2>World Map</h2>
        <div class="map-wrap">
          <canvas id="world" width="1000" height="560"></canvas>
          <div class="hud">
            <button id="playPause" title="Play or pause simulation animation">II</button>
            <input id="daySlider" type="range" min="0" value="0">
            <span class="day-label" id="dayLabel">Day 0</span>
          </div>
        </div>
        <div class="panel-body legend">
          <span><i class="dot" style="background:var(--green)"></i>farmer</span>
          <span><i class="dot" style="background:var(--gold)"></i>builder</span>
          <span><i class="dot" style="background:var(--red)"></i>hunter</span>
          <span><i class="dot" style="background:var(--blue)"></i>merchant</span>
          <span><i class="dot" style="background:var(--violet)"></i>blacksmith</span>
          <div class="agent-strip" id="agentStrip" style="flex-basis:100%"></div>
        </div>
      </article>
      <article class="panel">
        <h2>Trust Network</h2>
        <div class="panel-body"><svg id="trust"></svg></div>
      </article>
    </section>
    <section class="two">
      <article class="panel">
        <h2>Population Timeline</h2>
        <div class="panel-body"><canvas id="populationChart" width="900" height="300" style="height:260px"></canvas></div>
      </article>
      <article class="panel">
        <h2>Knowledge Graph</h2>
        <div class="panel-body"><svg id="knowledge"></svg></div>
      </article>
    </section>
    <section class="two">
      <article class="panel">
        <h2>Resources</h2>
        <div class="panel-body"><div class="bars" id="resources"></div></div>
      </article>
      <article class="panel">
        <h2>Innovation And Culture</h2>
        <div class="panel-body"><ul class="list" id="culture"></ul></div>
      </article>
      <article class="panel">
        <h2>Benchmark Scores</h2>
        <div class="panel-body"><div class="bars" id="benchmarks"></div></div>
      </article>
    </section>
  </main>
  <script>
    const DATA = __ARIA_WORLD_DATA__;
    const result = DATA.result || {};
    const summary = DATA.summary || {};
    const benchmark = DATA.benchmark || {};
    const agents = result.agent_statuses || [];
    const daily = result.daily_results || [];
    const populationHistory = result.world_state?.population_history || [];
    const maxDay = Math.max(0, (result.days_run || populationHistory.length || 1) - 1);
    let currentDay = maxDay;
    let playing = true;
    let lastAdvance = 0;
    const occupations = { farmer: 'var(--green)', builder: 'var(--gold)', hunter: 'var(--red)', merchant: 'var(--blue)', blacksmith: 'var(--violet)' };
    const css = getComputedStyle(document.documentElement);
    const colorFor = name => css.getPropertyValue(name).trim();
    const fmtPct = v => `${Math.round((v || 0) * 100)}%`;
    const fmt = v => Number.isFinite(v) ? String(Math.round(v * 100) / 100) : '0';
    document.getElementById('runBadge').textContent = `Seed ${result.seed ?? '?'} · Day ${summary.days ?? 0}`;

    function daySnapshot() {
      return daily[Math.min(currentDay, Math.max(daily.length - 1, 0))] || {};
    }

    function metricCard(label, value, color) {
      return `<div class="card"><div class="label">${label}</div><div class="value" style="color:${color}">${value}</div></div>`;
    }
    document.getElementById('metrics').innerHTML = [
      metricCard('Population', `${summary.initialPopulation || 0} -> ${summary.finalPopulation || 0}`, colorFor('--green')),
      metricCard('Food', fmt((result.world_state?.resources || {}).food || 0), colorFor('--gold')),
      metricCard('Resources', Object.keys(result.world_state?.resources || {}).length, colorFor('--cyan')),
      metricCard('Innovations', result.innovation_stats?.total_innovations || 0, colorFor('--violet')),
      metricCard('Culture', result.culture_stats?.active_customs || 0, colorFor('--blue')),
      metricCard('Benchmark', fmtPct(benchmark.overallScore || 0), colorFor('--green')),
    ].join('');
    const daySlider = document.getElementById('daySlider');
    const dayLabel = document.getElementById('dayLabel');
    daySlider.max = String(maxDay);
    daySlider.value = String(currentDay);
    daySlider.addEventListener('input', () => { currentDay = Number(daySlider.value); playing = false; updateControls(); });
    document.getElementById('playPause').addEventListener('click', () => { playing = !playing; updateControls(); });
    function updateControls() {
      daySlider.value = String(currentDay);
      dayLabel.textContent = `Day ${currentDay + 1}`;
      document.getElementById('playPause').textContent = playing ? 'II' : '>';
      renderTrust();
      renderAgentStrip();
    }
    updateControls();

    function agentPointsForDay() {
      const snap = daySnapshot();
      if (snap.agent_positions && snap.agent_positions.length) return snap.agent_positions;
      return [];
    }

    function drawEmptyCanvas(ctx, w, h, message) {
      ctx.fillStyle = colorFor('--muted');
      ctx.font = '15px system-ui';
      ctx.textAlign = 'center';
      ctx.fillText(message, w / 2, h / 2);
      ctx.textAlign = 'left';
    }
    function drawWorld(t) {
      const canvas = document.getElementById('world');
      const ctx = canvas.getContext('2d');
      const w = canvas.width, h = canvas.height;
      ctx.clearRect(0, 0, w, h);
      ctx.fillStyle = '#163135';
      ctx.fillRect(0, 0, w, h);
      ctx.fillStyle = '#263d2f';
      ctx.beginPath();
      ctx.moveTo(96, 88); ctx.bezierCurveTo(320, 18, 635, 34, 870, 132);
      ctx.bezierCurveTo(980, 240, 910, 448, 692, 508);
      ctx.bezierCurveTo(432, 574, 190, 474, 92, 332);
      ctx.bezierCurveTo(8, 222, 38, 126, 96, 88); ctx.fill();
      ctx.fillStyle = '#31543a';
      for (let i = 0; i < 34; i++) {
        const x = 70 + ((i * 179) % 860), y = 70 + ((i * 97) % 420);
        ctx.fillRect(x, y, 12 + (i % 4) * 6, 4);
      }
      const points = agentPointsForDay();
      if (!points.length) {
        drawEmptyCanvas(ctx, w, h, 'No real agent position snapshots for this day');
      }
      points.forEach(agent => {
        const p = { x: agent.x * w, y: agent.y * h };
        ctx.fillStyle = occupations[agent.occupation] ? colorFor(occupations[agent.occupation].slice(4, -1)) : colorFor('--cyan');
        ctx.globalAlpha = agent.alive ? 1 : 0.35;
        ctx.beginPath(); ctx.arc(p.x, p.y, 8 + Math.max(0, agent.happiness || 0) * 5, 0, Math.PI * 2); ctx.fill();
        ctx.globalAlpha = 1;
        ctx.fillStyle = '#eef4ee';
        ctx.font = '12px system-ui';
        ctx.fillText(agent.name, p.x + 12, p.y + 4);
      });
      if (playing && t - lastAdvance > 700) {
        currentDay = (currentDay + 1) % (maxDay + 1 || 1);
        lastAdvance = t;
        updateControls();
      }
      requestAnimationFrame(drawWorld);
    }
    requestAnimationFrame(drawWorld);

    function renderAgentStrip() {
      const snap = daySnapshot();
      const roster = snap.agent_statuses && snap.agent_statuses.length ? snap.agent_statuses : agents;
      document.getElementById('agentStrip').innerHTML = roster.slice(0, 12).map(a => {
        const color = occupations[a.occupation] ? colorFor(occupations[a.occupation].slice(4, -1)) : colorFor('--cyan');
        return `<div class="agent-pill"><i class="dot" style="background:${color};margin:0"></i><span><strong>${a.name}</strong><br>${a.occupation}</span><span>${Math.round((a.happiness || 0) * 100)}%</span></div>`;
      }).join('');
    }
    renderAgentStrip();

    function renderPopulationChart() {
      const canvas = document.getElementById('populationChart');
      const ctx = canvas.getContext('2d');
      const w = canvas.width, h = canvas.height;
      const values = populationHistory.length ? populationHistory : [summary.initialPopulation || 0, summary.finalPopulation || 0];
      const max = Math.max(1, ...values), min = Math.min(...values, 0);
      ctx.clearRect(0, 0, w, h);
      ctx.fillStyle = '#121815';
      ctx.fillRect(0, 0, w, h);
      ctx.strokeStyle = '#2e3932';
      ctx.lineWidth = 1;
      for (let i = 1; i < 5; i++) {
        const y = (h - 34) * i / 5 + 10;
        ctx.beginPath(); ctx.moveTo(44, y); ctx.lineTo(w - 18, y); ctx.stroke();
      }
      ctx.strokeStyle = colorFor('--green');
      ctx.lineWidth = 4;
      ctx.beginPath();
      values.forEach((v, i) => {
        const x = 44 + (w - 70) * i / Math.max(values.length - 1, 1);
        const y = h - 28 - ((v - min) / Math.max(max - min, 1)) * (h - 52);
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      });
      ctx.stroke();
      ctx.fillStyle = colorFor('--muted');
      ctx.font = '13px system-ui';
      ctx.fillText(`max ${max}`, 12, 22);
      ctx.fillText(`days ${values.length}`, 12, h - 12);
    }
    renderPopulationChart();

    function renderTrust() {
      const svg = document.getElementById('trust');
      const w = 520, h = 320, cx = w / 2, cy = h / 2, r = 112;
      svg.setAttribute('viewBox', `0 0 ${w} ${h}`);
      const snap = daySnapshot();
      const dayAgents = (snap.agent_statuses && snap.agent_statuses.length ? snap.agent_statuses : agents).slice(0, 14);
      if (!dayAgents.length) {
        svg.innerHTML = `<text x="${cx}" y="${cy}" text-anchor="middle" fill="${colorFor('--muted')}" font-size="14">No agent snapshots recorded</text>`;
        return;
      }
      const nodes = dayAgents.map((a, i, arr) => {
        const ang = Math.PI * 2 * i / Math.max(arr.length, 1);
        return { a, x: cx + Math.cos(ang) * r, y: cy + Math.sin(ang) * r };
      });
      const lines = [];
      const byId = new Map(nodes.map(n => [n.a.id || n.a.name, n]));
      if (snap.trust_edges && snap.trust_edges.length) {
        snap.trust_edges.forEach(edge => {
          const a = byId.get(edge.source);
          const b = byId.get(edge.target);
          if (!a || !b) return;
          const trust = (edge.trust || 0) / 100;
          lines.push(`<line x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}" stroke="${trust > 0.65 ? colorFor('--green') : colorFor('--line')}" stroke-width="${1 + trust * 3}" opacity="${0.25 + trust * 0.55}"/>`);
        });
      }
      const empty = lines.length ? '' : `<text x="${cx}" y="${h - 18}" text-anchor="middle" fill="${colorFor('--muted')}" font-size="12">No trust edges above the simulation threshold on this day</text>`;
      svg.innerHTML = lines.join('') + nodes.map(n => `<g><circle cx="${n.x}" cy="${n.y}" r="13" fill="${colorFor('--panel-2')}" stroke="${colorFor('--cyan')}" stroke-width="2"/><text x="${n.x}" y="${n.y + 31}" text-anchor="middle" fill="${colorFor('--muted')}" font-size="11">${n.a.name}</text></g>`).join('') + empty;
    }
    renderTrust();

    function renderKnowledge() {
      const svg = document.getElementById('knowledge');
      const bySkill = result.knowledge_stats?.by_skill || {};
      const skills = Object.entries(bySkill);
      const w = 560, h = 320, cx = w / 2, cy = h / 2;
      svg.setAttribute('viewBox', `0 0 ${w} ${h}`);
      if (!skills.length) {
        svg.innerHTML = `<text x="${cx}" y="${cy}" text-anchor="middle" fill="${colorFor('--muted')}" font-size="14">No knowledge-sharing stats recorded</text>`;
        return;
      }
      const nodes = skills.map(([name, stats], i) => {
        const a = Math.PI * 2 * i / Math.max(skills.length, 1);
        return { name, stats, x: cx + Math.cos(a) * 130, y: cy + Math.sin(a) * 95 };
      });
      svg.innerHTML = `<circle cx="${cx}" cy="${cy}" r="34" fill="${colorFor('--panel-2')}" stroke="${colorFor('--gold')}" stroke-width="2"/><text x="${cx}" y="${cy + 4}" text-anchor="middle" fill="${colorFor('--text')}" font-size="13">Knowledge</text>` +
        nodes.map(n => `<line x1="${cx}" y1="${cy}" x2="${n.x}" y2="${n.y}" stroke="${colorFor('--line')}" stroke-width="2"/>`).join('') +
        nodes.map(n => `<g><circle cx="${n.x}" cy="${n.y}" r="${14 + (n.stats.avg_level || 0) * 18}" fill="${colorFor('--panel-2')}" stroke="${colorFor('--violet')}" stroke-width="2"/><text x="${n.x}" y="${n.y + 4}" text-anchor="middle" fill="${colorFor('--text')}" font-size="12">${n.name}</text></g>`).join('');
    }
    renderKnowledge();

    function barRow(label, value, max, color) {
      const pct = max > 0 ? Math.max(0, Math.min(1, value / max)) : 0;
      return `<div class="bar-row"><span>${label}</span><div class="bar-track"><div class="bar-fill" style="width:${pct * 100}%;background:${color}"></div></div><strong>${fmt(value)}</strong></div>`;
    }
    const resources = result.world_state?.resources || {};
    const maxResource = Math.max(1, ...Object.values(resources));
    document.getElementById('resources').innerHTML = Object.keys(resources).length
      ? Object.entries(resources).map(([k, v], i) => barRow(k, v, maxResource, [colorFor('--green'), colorFor('--gold'), colorFor('--blue'), colorFor('--red'), colorFor('--violet'), colorFor('--cyan')][i % 6])).join('')
      : '<div class="sub">No world resource telemetry recorded.</div>';

    const culture = result.culture_stats || {}, innovation = result.innovation_stats || {};
    document.getElementById('culture').innerHTML = [
      `Recipes discovered: ${innovation.total_recipes || 0}`,
      `Innovations made: ${innovation.total_innovations || 0}`,
      `Average efficiency: ${fmt(innovation.average_efficiency || 0)}`,
      `Active customs: ${culture.active_customs || 0}`,
      `Strong customs: ${culture.strong_customs || 0}`,
      `Cultural adherence: ${fmtPct(culture.average_adherence || 0)}`,
    ].map(x => `<li>${x}</li>`).join('');

    const metricRows = (benchmark.metrics || []).map(m => barRow(m.name.replace('simulation_', ''), m.value || 0, 1, colorFor('--green')));
    const resultRows = (benchmark.results || []).map(r => barRow(r.task_name.replace('simulation_', ''), r.score || 0, 1, r.success ? colorFor('--green') : colorFor('--red')));
    document.getElementById('benchmarks').innerHTML = metricRows.length || resultRows.length
      ? [barRow('overall', benchmark.overallScore || 0, 1, colorFor('--gold')), ...metricRows, ...resultRows].join('')
      : '<div class="sub">No benchmark result attached to this dashboard run.</div>';
  </script>
</body>
</html>"""
