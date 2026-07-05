"""Generates a self-contained HTML cost/decision dashboard from
data/logs/decisions_log.csv.

Usage: python -m dashboard.dashboard
Writes dashboard/report.html.
"""

import csv
import html
import os

from src import config, metrics, status_check, trace_logger

REPORT_PATH = os.path.join(os.path.dirname(__file__), "report.html")

# Fixed slot per decision source, never reassigned based on what's present.
SOURCE_COLORS = {
    "local": "#2a78d6",
    "escalated_to_gemini": "#1baf7a",
    "escalated_to_human": "#eda100",
}
SOURCE_LABELS = {
    "local": "Local (Ollama, $0)",
    "escalated_to_gemini": "Escalated to Gemini",
    "escalated_to_human": "Escalated to human",
}
# human_confirmed rows are a follow-up on an existing escalated_to_human row,
# not a fourth independent category, so they're left out of the percentage
# bars (they wouldn't sum to 100% otherwise) and shown as their own tile.

# Status palette — fixed, never reused for the categorical series above.
STATUS_COLORS = {
    "ok": "#0ca30c",
    "warning": "#fab219",
    "critical": "#d03b3b",
    "not_configured": "#8a8a86",
}
STATUS_LABELS = {
    "ok": "Online",
    "warning": "Degraded",
    "critical": "Offline",
    "not_configured": "Not configured",
}


def _read_rows() -> list[dict]:
    if not os.path.exists(config.DECISIONS_LOG_PATH):
        return []
    with open(config.DECISIONS_LOG_PATH, newline="") as f:
        return list(csv.DictReader(f))


def _bar(label: str, count: int, total: int, color: str) -> str:
    pct = round(100 * count / total, 1) if total else 0.0
    return f"""
    <div class="bar-row">
      <div class="bar-label">{html.escape(label)}</div>
      <div class="bar-track">
        <div class="bar-fill" style="width:{pct}%; background:{color};"></div>
      </div>
      <div class="bar-value">{count} ({pct}%)</div>
    </div>"""


def _cost_bar(label: str, value: float, max_value: float, color: str) -> str:
    pct = round(100 * value / max_value, 1) if max_value else 0.0
    return f"""
    <div class="bar-row">
      <div class="bar-label">{html.escape(label)}</div>
      <div class="bar-track">
        <div class="bar-fill" style="width:{pct}%; background:{color};"></div>
      </div>
      <div class="bar-value">${value:.4f}</div>
    </div>"""


def _status_card(entry: dict) -> str:
    status = entry["status"]
    color = STATUS_COLORS.get(status, STATUS_COLORS["not_configured"])
    label = STATUS_LABELS.get(status, status)
    return f"""
    <div class="status-card">
      <div class="status-row">
        <span class="status-dot" style="background:{color};"></span>
        <span class="status-name">{html.escape(entry['name'])}</span>
        <span class="status-badge" style="color:{color};">{html.escape(label)}</span>
      </div>
      <div class="status-detail">{html.escape(entry['detail'])}</div>
    </div>"""


def _decision_pill(decision: dict | None) -> str:
    if not decision:
        return "<span class='muted'>—</span>"
    return (
        f"<strong>{html.escape(str(decision.get('action')))}</strong> "
        f"(confidence {decision.get('confidence')})<br>"
        f"<span class='muted'>{html.escape(str(decision.get('reasoning', '')))}</span>"
    )


def _trace_card(entry: dict) -> str:
    snapshot_line = ", ".join(
        f"{k}={v}" for k, v in entry["snapshot"].items() if k not in ("zone_id",)
    )
    discussion = f"""
        <div class="discussion-col">
          <div class="discussion-role">Local Decision Agent (Ollama)</div>
          {_decision_pill(entry['local_decision'])}
        </div>"""
    if entry["escalated"]:
        discussion += f"""
        <div class="discussion-col">
          <div class="discussion-role">Cloud Reasoning Agent (Gemini)</div>
          {_decision_pill(entry['cloud_decision'])}
        </div>"""

    resolution_line = ""
    if entry["resolution"] == "human_confirmed":
        resolution_line = "<div class='muted'>Resolved by farm owner's Telegram reply</div>"
    elif entry["resolution"]:
        resolution_line = f"<div class='muted'>Consensus: <strong>{html.escape(entry['resolution'])}</strong></div>"

    notification_line = ""
    if entry["notification_channel"]:
        notification_line = f"<div class='muted'>Notification sent via: <strong>{html.escape(entry['notification_channel'])}</strong></div>"

    return f"""
    <div class="trace-card">
      <div class="trace-header">
        <span>{html.escape(entry['timestamp'])}</span>
        <span class="muted">zone={html.escape(entry['zone_id'])}</span>
      </div>
      <div class="muted trace-snapshot">Sensor snapshot: {html.escape(snapshot_line)}</div>
      <div class="discussion">{discussion}</div>
      {resolution_line}
      <div>Final action: <strong>{html.escape(entry['final_action'])}</strong>
        {f"<span class='muted'>({html.escape(entry['block_reason'])})</span>" if entry.get('block_reason') else ''}</div>
      {notification_line}
    </div>"""


def _traces_html(entries: list[dict]) -> str:
    if not entries:
        return "<p class='muted'>No agent activity logged yet.</p>"
    return "\n".join(_trace_card(e) for e in reversed(entries))


def _table(rows: list[dict]) -> str:
    if not rows:
        return "<p class='muted'>No decisions logged yet.</p>"
    body = "\n".join(
        f"<tr><td>{html.escape(r['timestamp'])}</td><td>{html.escape(r['zone_id'])}</td>"
        f"<td>{html.escape(SOURCE_LABELS.get(r['decision_source'], r['decision_source']))}</td>"
        f"<td>{html.escape(r['action'])}</td><td>{html.escape(r['confidence'])}</td>"
        f"<td>{html.escape(r['block_reason'])}</td><td>${float(r['estimated_cost_usd']):.4f}</td></tr>"
        for r in rows
    )
    return f"""
    <table>
      <thead><tr><th>Timestamp</th><th>Zone</th><th>Source</th><th>Action</th>
      <th>Confidence</th><th>Block reason</th><th>Cost</th></tr></thead>
      <tbody>{body}</tbody>
    </table>"""


def generate(auto_refresh_seconds: int | None = None) -> str:
    """auto_refresh_seconds: if set, the page reloads itself on that interval
    — used by live_monitor.py so an already-open browser tab stays current."""
    rows = _read_rows()
    summary = metrics.summary()
    total = summary.get("total_decisions", 0)

    status_cards = "".join(_status_card(entry) for entry in status_check.all_statuses())
    traces_html = _traces_html(trace_logger.read_all())

    source_counts = {source: 0 for source in SOURCE_COLORS}
    for r in rows:
        if r["decision_source"] in source_counts:
            source_counts[r["decision_source"]] += 1

    source_bars = "\n".join(
        _bar(SOURCE_LABELS[source], count, total, SOURCE_COLORS[source])
        for source, count in source_counts.items()
    )

    actual_cost = summary.get("actual_cost_usd", 0.0)
    hypothetical_cost = summary.get("hypothetical_all_cloud_cost_usd", 0.0)
    max_cost = max(actual_cost, hypothetical_cost, 0.0001)
    cost_bars = (
        _cost_bar("Actual (cost-aware cascade)", actual_cost, max_cost, "#2a78d6")
        + _cost_bar("Hypothetical (all-cloud)", hypothetical_cost, max_cost, "#e34948")
    )

    stat_tiles = "".join(
        f"<div class='tile'><div class='tile-value'>{value}</div><div class='tile-label'>{label}</div></div>"
        for label, value in [
            ("Total decisions", total),
            ("Savings vs. all-cloud", f"{summary.get('savings_pct', 0)}%"),
            ("Actual cost", f"${actual_cost:.4f}"),
            ("Hypothetical all-cloud cost", f"${hypothetical_cost:.4f}"),
            ("Human confirmations via Telegram", summary.get("human_confirmations", 0)),
        ]
    )

    refresh_tag = (
        f'<meta http-equiv="refresh" content="{auto_refresh_seconds}">'
        if auto_refresh_seconds else ""
    )
    live_banner = (
        f"<p class='subtitle'>Live mode — refreshing every {auto_refresh_seconds}s</p>"
        if auto_refresh_seconds else ""
    )

    return f"""<!doctype html>
<html lang="en">
<head>
{refresh_tag}
<meta charset="utf-8">
<title>AgriGuard — Cost &amp; Decision Dashboard</title>
<style>
  :root {{
    --surface-1: #fcfcfb; --text-primary: #0b0b0b; --text-secondary: #52514e;
    --border: #e3e2dc;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --surface-1: #1a1a19; --text-primary: #ffffff; --text-secondary: #c3c2b7; --border: #3a3a37; }}
  }}
  :root[data-theme="dark"] {{ --surface-1: #1a1a19; --text-primary: #ffffff; --text-secondary: #c3c2b7; --border: #3a3a37; }}
  :root[data-theme="light"] {{ --surface-1: #fcfcfb; --text-primary: #0b0b0b; --text-secondary: #52514e; --border: #e3e2dc; }}
  body {{ background: var(--surface-1); color: var(--text-primary); font-family: system-ui, sans-serif; margin: 0; padding: 2rem; }}
  h1 {{ font-size: 1.4rem; margin-bottom: 0.25rem; }}
  .subtitle {{ color: var(--text-secondary); margin-bottom: 2rem; }}
  .tiles {{ display: flex; gap: 1rem; flex-wrap: wrap; margin-bottom: 2rem; }}
  .tile {{ border: 1px solid var(--border); border-radius: 8px; padding: 1rem 1.5rem; min-width: 160px; }}
  .tile-value {{ font-size: 1.6rem; font-weight: 600; }}
  .tile-label {{ color: var(--text-secondary); font-size: 0.85rem; margin-top: 0.25rem; }}
  section {{ margin-bottom: 2rem; }}
  h2 {{ font-size: 1.05rem; margin-bottom: 1rem; }}
  .bar-row {{ display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.6rem; }}
  .bar-label {{ width: 220px; font-size: 0.9rem; color: var(--text-secondary); flex-shrink: 0; }}
  .bar-track {{ flex: 1; background: var(--border); border-radius: 4px; height: 18px; overflow: hidden; }}
  .bar-fill {{ height: 100%; border-radius: 4px; }}
  .bar-value {{ width: 110px; text-align: right; font-size: 0.85rem; flex-shrink: 0; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 0.85rem; }}
  th, td {{ border-bottom: 1px solid var(--border); padding: 0.4rem 0.6rem; text-align: left; }}
  th {{ color: var(--text-secondary); font-weight: 500; }}
  .muted {{ color: var(--text-secondary); }}
  .table-wrap {{ overflow-x: auto; }}
  .status-grid {{ display: flex; gap: 1rem; flex-wrap: wrap; }}
  .status-card {{ border: 1px solid var(--border); border-radius: 8px; padding: 0.9rem 1.1rem; min-width: 260px; flex: 1; }}
  .status-row {{ display: flex; align-items: center; gap: 0.5rem; }}
  .status-dot {{ width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }}
  .status-name {{ font-weight: 600; font-size: 0.9rem; }}
  .status-badge {{ margin-left: auto; font-size: 0.8rem; font-weight: 600; }}
  .status-detail {{ color: var(--text-secondary); font-size: 0.8rem; margin-top: 0.35rem; }}
  .trace-card {{ border: 1px solid var(--border); border-radius: 8px; padding: 1rem; margin-bottom: 1rem; font-size: 0.88rem; }}
  .trace-header {{ display: flex; justify-content: space-between; font-size: 0.8rem; margin-bottom: 0.5rem; }}
  .trace-snapshot {{ font-size: 0.8rem; margin-bottom: 0.75rem; }}
  .discussion {{ display: flex; gap: 1rem; flex-wrap: wrap; margin-bottom: 0.5rem; }}
  .discussion-col {{ flex: 1; min-width: 260px; background: var(--border); border-radius: 6px; padding: 0.6rem 0.8rem; }}
  .discussion-role {{ font-weight: 600; font-size: 0.8rem; margin-bottom: 0.3rem; }}
</style>
</head>
<body>
  <h1>AgriGuard — Cost &amp; Decision Dashboard</h1>
  <p class="subtitle">Cost-aware multi-agent crop monitoring — decision source breakdown and cascading-cost savings</p>
  {live_banner}

  <section>
    <h2>Agent / bot status</h2>
    <div class="status-grid">{status_cards}</div>
  </section>

  <div class="tiles">{stat_tiles}</div>

  <section>
    <h2>Decisions by source</h2>
    {source_bars}
  </section>

  <section>
    <h2>Cost: cascading vs. all-cloud baseline</h2>
    {cost_bars}
  </section>

  <section>
    <h2>Agent activity — sensor data, model reasoning, and the local/cloud "discussion"</h2>
    {traces_html}
  </section>

  <section>
    <h2>Decision log</h2>
    <div class="table-wrap">{_table(rows)}</div>
  </section>
</body>
</html>"""


if __name__ == "__main__":
    report_html = generate()
    with open(REPORT_PATH, "w") as f:
        f.write(report_html)
    print(f"Dashboard written to {REPORT_PATH}")
