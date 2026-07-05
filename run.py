"""Single entry point for AgriGuard: runs the full scripted-scenario demo,
regenerates the dashboard, and prints where to open it.

Usage: python run.py   (or ./run.sh, which activates the project's venv first)
"""

import os
import re

# Every path in this project is relative to agriguard/, so make sure we're
# there no matter where this script was actually invoked from.
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from src import config
from src.orchestrator import run_scripted_scenarios


def _clear_previous_run_logs():
    for path in (config.DECISIONS_LOG_PATH, "data/logs/agent_trace.jsonl"):
        if os.path.exists(path):
            os.remove(path)


def _windows_path(abs_posix_path: str) -> str | None:
    """If running under WSL (/mnt/<drive>/...), return the Windows-native
    C:\\... equivalent for pasting into a Windows browser."""
    match = re.match(r"^/mnt/([a-zA-Z])/(.*)$", abs_posix_path)
    if not match:
        return None
    drive, rest = match.groups()
    return f"{drive.upper()}:\\{rest.replace('/', chr(92))}"


def main():
    print("=" * 70)
    print("AgriGuard — running the 6 scripted scenarios (sensors -> agents -> actuator)")
    print("This is a one-shot demo: it runs once and exits — no Telegram replies or chat")
    print("work here. For that, stop this and run ./run.sh (or python -m src.live_monitor)")
    print("=" * 70)

    _clear_previous_run_logs()
    run_scripted_scenarios()

    print("\n" + "=" * 70)
    print("Generating dashboard (cost summary, agent/bot status, full agent trace)...")
    print("=" * 70)
    from dashboard.dashboard import REPORT_PATH, generate

    with open(REPORT_PATH, "w") as f:
        f.write(generate())

    abs_path = os.path.abspath(REPORT_PATH)
    dashboard_url = f"file://{abs_path}"
    print(f"\nDashboard ready — open this in your browser:\n\n  {dashboard_url}")

    win_path = _windows_path(abs_path)
    if win_path:
        print(f"\nOn WSL, your Windows browser needs this path instead:\n\n  {win_path}")


if __name__ == "__main__":
    main()
