---
name: build-kaggle-notebook
description: Build/update notebooks/kaggle_submission_notebook.ipynb — the actual judged Kaggle deliverable. Installs and serves Ollama self-contained inside the Kaggle kernel with an idempotent model-pull check, ports the src/ agent logic into notebook cells, runs the 6 scripted scenarios, and writes up the required-concepts mapping.
---

# Build Kaggle Submission Notebook

Produces `notebooks/kaggle_submission_notebook.ipynb`, the file judges actually open — per Section 3b-i and Section 11 of `AgriGuard_Project_Plan.md`, this must be re-runnable end-to-end on Kaggle's infrastructure, not just a writeup describing a local setup. Only build this once `run-local-demo` (Must-have) and ideally `build-cloud-escalation` (Should-have) already work locally — port working code into the notebook, don't develop fresh inside it.

## Design constraints (from the plan)

- **Ollama runs self-contained inside the Kaggle kernel** using Kaggle's free GPU quota (T4, 16GB) — this is the decision from Section 3b-i, not a local-only demo with a recorded video as fallback.
- **Idempotent model pull — never blind-pull.** First cells must check `ollama list` for the model tag before calling `ollama pull`; re-running the notebook without restarting the kernel should not re-trigger a ~9.6GB download. See Section 3b-i for the exact shell snippet to adapt.
- Confirm Kaggle notebook internet access is enabled (Settings → Internet: On) before relying on `ollama pull` / Gemini API calls inside the kernel.
- Keep `OLLAMA_HOST` configurable exactly as `src/config.py` already does — the notebook should import/reuse the `src/` package rather than reimplementing agent logic inline, so local and Kaggle runs stay in sync. (Upload `src/` alongside the notebook, or `%%writefile` it into the kernel working directory in an early cell.)
- Model pull is ~9.6GB (confirmed size, larger than originally estimated) — budget kernel session time accordingly and test this early, not right before the deadline.
- The notebook is also the write-up: it must explicitly map the implementation to the 3+ required competition concepts (Section 4's numbered list: ADK-based multi-agent system, security/safety feature, cost-optimization/model routing, plus concierge/MCP if the stretch tier landed) and explicitly state that sensors/actuators are simulated with a clear path to real hardware (Section 2).

## Structure to produce

1. **Setup cells** — install Ollama, start `ollama serve` in the background, idempotent-check-then-pull the model, install `requirements.txt` (`google-adk`, `litellm`, etc.).
2. **Code cells** — import/write out the `src/` package (sensors, agents, orchestrator, metrics) so the notebook runs the *same* code as local dev, not a reimplementation.
3. **Demo cells** — run `run_scripted_scenarios()` from `src/orchestrator.py`, printing each scenario's decision path and the final cost summary from `src/metrics.summary()`.
4. **Cost-savings section** — render the summary (Section 9) as a clear before/after comparison (actual cascading cost vs. hypothetical all-cloud cost), since this is called out as the most memorable section for judges.
5. **Write-up markdown cells** — problem statement, architecture diagram/description, required-concepts mapping, simulated-vs-real disclosure, and (if built) the llama.cpp production-path note from Section 3b.

## Verification

Before calling this done: actually run the notebook top-to-bottom in a fresh Kaggle kernel session (not just locally) to confirm the in-kernel Ollama install + idempotent pull + full scenario run completes within a single session without manual intervention. If it doesn't, fall back per Section 3b-i: local run + recorded demo video + notebook as writeup — don't burn more than a few hours past a failed attempt before switching.
