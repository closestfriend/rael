(() => {
  "use strict";
  const root = document.getElementById("app");
  let data = JSON.parse(document.getElementById("experiment-data").textContent);
  let selected = data.runs.find((r) => r.stage === "baseline")?.id;
  let view = "matrix",
    stage = "baseline",
    query = "",
    filter = "all",
    eventFilter = "all";
  const esc = (value) =>
    String(value ?? "").replace(
      /[&<>"']/g,
      (c) =>
        ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#39;",
        })[c],
    );
  const fmt = (n, places = 2) => (n == null ? "—" : Number(n).toFixed(places));
  const pct = (n) => (n == null ? "—" : `${Math.round(n * 100)}%`);
  const status = (value) =>
    value == null ? "Unscored" : value ? "Pass" : "Fail";
  const cls = (value) => (value == null ? "missing" : value ? "pass" : "fail");
  const tone = (value) => (value == null ? "" : value ? "good" : "bad");
  const groups = () =>
    data.runs
      .filter((r) => r.stage === "baseline")
      .map((before) => ({
        before,
        after: data.runs.find((r) => r.parent_id === before.id),
      }));
  const selectedGroup = () =>
    groups().find((g) => g.before.id === selected) || groups()[0];
  function visibleGroups() {
    return groups().filter((g) => {
      const r = g[stage === "baseline" ? "before" : "after"];
      const text =
        `${g.before.task.id} ${g.before.task.prompt} ${g.before.task.tags.join(" ")}`.toLowerCase();
      if (!text.includes(query.toLowerCase())) return false;
      if (filter === "confidence")
        return (
          r?.metrics.objective_false_confidence ||
          r?.metrics.objective_false_pessimism
        );
      if (filter === "disagreement") return r?.metrics.judge_disagreement > 0;
      if (filter === "regression")
        return (
          g.before.metrics.objective_passed === true &&
          g.after?.metrics.objective_passed === false
        );
      if (filter === "tools") return r?.metrics.tool_calls > 0;
      return true;
    });
  }
  function scoreMark(run, key, group) {
    const verdict =
      key === "objective"
        ? run?.objective
        : run?.verdicts.find((v) => v.evaluator_id === key);
    const valid = verdict?.status === "ok";
    const passed = valid ? verdict.passed : null;
    const value = valid
      ? key === "objective"
        ? passed
          ? "✓"
          : "×"
        : fmt(verdict.score, 1)
      : "—";
    const label = `${group.before.task.id}, ${run?.stage || "revision unavailable"}, ${key}: ${valid ? `${status(passed)}, score ${fmt(verdict.score)}` : verdict?.status || "unavailable"}`;
    return `<button class="mark ${cls(passed)} ${run?.stage === stage ? "active" : ""}" data-select="${esc(group.before.id)}" data-stage="${run?.stage || "revision"}" title="${esc(label)}" aria-label="${esc(label)}">${value}</button>`;
  }
  function matrix() {
    const list = visibleGroups();
    if (!list.length)
      return '<div class="empty">No tasks match this filter. Try All tasks or clear the search.</div>';
    return `<div class="table-wrap"><table><caption>Each cell shows baseline / revision. Select a cell to inspect the recorded attempt.</caption><thead><tr><th scope="col">Task<small>${list.length} of ${groups().length} pairs shown</small></th><th scope="col">Objective<small>reference</small></th>${data.config.evaluators.map((e) => `<th scope="col">${esc(e.id)}<small>${esc(e.kind)}</small></th>`).join("")}<th scope="col">Predict<small>panel pass</small></th></tr></thead><tbody>${list
      .map((g) => {
        const r = stage === "baseline" ? g.before : g.after;
        return `<tr class="${g.before.id === selected ? "selected" : ""}"><td><button class="task-button" data-select="${esc(g.before.id)}">${esc(g.before.task.id)}<span>seed ${g.before.seed} / repeat ${g.before.repetition + 1}</span></button></td>${["objective", ...data.config.evaluators.map((e) => e.id)].map((key) => `<td><div class="mini-pair">${scoreMark(g.before, key, g)}${scoreMark(g.after, key, g)}</div></td>`).join("")}<td class="score-number">${pct(r?.prediction?.pass_probability)}</td></tr>`;
      })
      .join("")}</tbody></table></div>`;
  }
  function gap() {
    const list = visibleGroups();
    if (!list.length)
      return '<div class="empty">No tasks match this filter.</div>';
    return `<div class="gap-scale"><span>Predicted / observed</span><div class="gap-axis"><span>0</span><span>.25</span><span>.50</span><span>.75</span><span>1</span></div><span style="text-align:right">Truth</span></div>${list
      .map((g) => {
        const r = stage === "baseline" ? g.before : g.after;
        const p = r?.prediction?.predicted_score,
          actual = r?.metrics.judge_mean_score;
        const valid = p != null && actual != null;
        const left = valid ? Math.min(p, actual) * 100 : 0,
          width = valid ? Math.abs(p - actual) * 100 : 0;
        const label = `${g.before.task.id}: predicted mean ${fmt(p)}, observed mean ${fmt(actual)}, objective ${status(r?.metrics.objective_passed)}`;
        return `<button class="gap-row ${g.before.id === selected ? "selected" : ""}" data-select="${esc(g.before.id)}" title="${esc(label)}" aria-label="${esc(label)}"><span>${esc(g.before.task.id)}</span><span class="gap-track">${valid ? `<i class="link" style="left:${left}%;width:${width}%"></i><i class="predicted" style="left:${p * 100}%"></i><i class="observed" style="left:${actual * 100}%"></i>` : "Unscored"}</span><span class="gap-outcome ${tone(r?.metrics.objective_passed)}">${r?.metrics.objective_passed == null ? "?" : r.metrics.objective_passed ? "✓" : "×"}</span></button>`;
      })
      .join(
        "",
      )}<div class="legend"><span><i class="swatch predicted" style="border-radius:50%"></i>Predicted mean score</span><span><i class="swatch observed" style="border-radius:50%"></i>Observed judge mean</span></div><p class="footnote">Longer connections expose larger prediction errors. Truth at right is the independent objective check. Incomplete panels show their available mean; calibration is withheld.</p>`;
  }
  function answer(run, label) {
    if (!run)
      return `<div class="answer"><h3>${label}</h3><p class="subtle">No revision recorded.</p></div>`;
    return `<div class="answer"><h3>${label}<span class="${tone(run.metrics.objective_passed)}">${status(run.metrics.objective_passed)}</span></h3><p class="answer-output">${esc(run.answer ?? "No complete answer")}</p><dl><dt>Predicted panel pass</dt><dd>${pct(run.prediction?.pass_probability)}</dd><dt>Predicted mean score</dt><dd>${fmt(run.prediction?.predicted_score)}</dd><dt>Observed judge mean</dt><dd>${fmt(run.metrics.judge_mean_score)}</dd><dt>Objective confidence</dt><dd>${pct(run.prediction?.confidence)}</dd><dt>Panel Brier error</dt><dd>${fmt(run.metrics.panel_brier, 3)}</dd></dl><div class="run-id">${esc(run.id)} · ${esc(run.status)}</div>${run.errors.length ? `<p class="bad subtle">${esc(run.errors.join("; "))}</p>` : ""}</div>`;
  }
  const names = {
    task_received: "Task received",
    model_call: "Model request",
    model_result: "Model response",
    tool_call: "Tool call",
    tool_result: "Tool observation",
    final_answer: "Final answer",
    prediction: "Prediction sealed",
    evaluation_start: "Evaluation boundary",
    objective_result: "Objective check",
    evaluator_call: "Evaluator request",
    evaluator_result: "Evaluator verdict",
    intervention: "Intervention applied",
    run_finished: "Attempt finished",
    retry: "Retry scheduled",
    error: "Request error",
    stage_error: "Stage error",
  };
  function inspector() {
    const g = selectedGroup();
    if (!g)
      return '<div class="empty">No attempts have been recorded yet.</div>';
    const run = stage === "baseline" ? g.before : g.after;
    const task = g.before.task;
    const comparison = data.metrics.pairs.comparisons.find(
      (p) => p.before === g.before.id,
    );
    const events = (run?.trace || []).filter(
      (e) =>
        eventFilter === "all" ||
        (eventFilter === "tools"
          ? e.type.startsWith("tool_")
          : eventFilter === "evaluation"
            ? ["evaluation", "judge"].includes(e.phase)
            : ["answer", "prediction", "critique"].includes(e.phase)),
    );
    return `<div class="detail-header"><div><span class="task-index">Selected task / ${esc(task.expected_output_type)}</span><h2>${esc(task.id)}</h2></div><div class="stage-tabs" aria-label="Attempt">${["baseline", "revision"].map((s) => `<button data-attempt="${s}" aria-pressed="${stage === s}">${s === "baseline" ? "Before" : "After"}</button>`).join("")}</div></div><p class="prompt">${esc(task.prompt)}</p><div class="tags">${task.tags.map((t) => `<span>${esc(t)}</span>`).join("")}</div><div class="answers">${answer(g.before, "Before")}${answer(g.after, "After")}</div><div class="delta"><span>Judge score Δ <b>${fmt(comparison?.score_delta)}</b></span><span>Objective <b>${comparison?.objective_improved ? "improved" : comparison?.objective_regressed ? "regressed" : comparison?.objective_improved === false ? "unchanged" : "unavailable"}</b></span></div><details class="judgments"><summary>${run?.verdicts.length || 0} individual verdicts / ${esc(stage)}</summary>${(run?.verdicts || []).map((v) => `<div class="judge"><strong>${esc(v.evaluator_id)}</strong> <span class="${tone(v.passed)}">${v.status === "ok" ? `${status(v.passed)} ${fmt(v.score)}` : esc(v.status)}</span><p>${esc(v.rationale || v.error || "")}</p><small>version ${esc(v.version)} / confidence ${pct(v.confidence)}</small>${v.evidence?.length ? `<p>Evidence: ${esc(v.evidence.join(" / "))}</p>` : ""}</div>`).join("")}</details>${run?.intervention ? `<details class="judgments"><summary>Intervention / ${esc(run.intervention.kind)}</summary><p class="subtle">${esc(run.intervention.text)}</p></details>` : ""}<div class="trace"><div class="trace-head"><h3>Observable trace <span class="subtle">/ ${run?.trace.length || 0} events</span></h3><select id="event-filter" aria-label="Filter trace events">${[
      ["all", "All events"],
      ["agent", "Agent"],
      ["tools", "Tools"],
      ["evaluation", "Evaluation"],
    ]
      .map(
        ([v, l]) =>
          `<option value="${v}" ${eventFilter === v ? "selected" : ""}>${l}</option>`,
      )
      .join(
        "",
      )}</select></div><div class="trace-list">${events.length ? events.map((e) => `<details class="event ${esc(e.type)}"><summary><span class="seq">${String(e.seq + 1).padStart(2, "0")}</span><span>${esc(names[e.type] || e.type)}</span><span class="phase">${esc(e.phase)}</span></summary><pre>${esc(JSON.stringify({ timestamp: e.timestamp, ...e.data }, null, 2))}</pre></details>`).join("") : '<p class="subtle">No events in this selection.</p>'}</div><p class="trace-note">Observable messages and actions only. Expand an event for its exact recorded payload.</p></div>`;
  }
  function render() {
    const metrics = data.metrics.stages[stage] || {},
      resources = data.metrics.resources;
    root.innerHTML = `<div class="shell"><header class="masthead"><div class="brand"><span class="brand-mark" aria-hidden="true"><i></i><i></i><i></i></span>RAEL</div><p>Agent behavior, under observation.</p><div class="actions"><span class="edition">Research instrument / v0.1</span><label class="file">Open result.json<input id="load-file" type="file" accept=".json,application/json" aria-label="Open experiment JSON"></label></div></header><div id="load-error" class="error-banner hidden" role="alert"></div><section class="intro"><div><h1>Trace. Signal. Failure.</h1><p>What an agent thinks it did. What the judges saw.<br>What actually happened.</p></div><div class="experiment-meta"><strong>${esc(data.name)}</strong>${esc(data.config.agent.provider)} / ${esc(data.config.agent.model)}<br>${data.tasks.length} tasks · ${data.runs.length} attempts · ${esc(data.status)}</div></section>${data.manifest.synthetic_agent ? '<div class="fixture"><strong>Scripted fixture</strong><span>These are real harness records from a deterministic mock provider. They demonstrate the instrument, not model performance.</span></div>' : '<div class="fixture"><strong>Live model records</strong><span>Judge configurations are separate observations. Shared model families can have correlated errors.</span></div>'}<div class="status-ribbon"><span>Attempt <b>${stage}</b></span><span>Objective success <b>${pct(metrics.objective_success_rate)}</b></span><span>Panel Brier ↓ <b>${fmt(metrics.panel_brier, 3)}</b></span><span>Judge disagreement <b>${pct(metrics.judge_disagreement)}</b></span><span>Scored panels <b>${metrics.complete_panels ?? 0}/${metrics.attempts ?? 0}</b></span></div><main id="workspace" class="workspace"><section class="matrix-section" aria-label="Experiment overview"><div class="panel-heading"><h2>Different observers. Same answer.</h2><div class="view-tabs" aria-label="Overview view"><button data-view="matrix" aria-pressed="${view === "matrix"}">Matrix</button><button data-view="gap" aria-pressed="${view === "gap"}">Confidence gap</button></div></div><div class="toolbar"><input id="search" type="search" placeholder="Find a task or behavior…" aria-label="Search tasks" value="${esc(query)}"><select id="filter" aria-label="Filter tasks">${[
      ["all", "All tasks"],
      ["confidence", "Confidence errors"],
      ["disagreement", "Judge disagreement"],
      ["regression", "Revision regressions"],
      ["tools", "Tool use"],
    ]
      .map(
        ([v, l]) =>
          `<option value="${v}" ${filter === v ? "selected" : ""}>${l}</option>`,
      )
      .join(
        "",
      )}</select></div><div class="legend"><span><i class="swatch pass"></i>Pass</span><span><i class="swatch fail"></i>Fail</span><span><i class="swatch missing"></i>Unscored</span><span>Scores 0–1 / each judge keeps its own verdict</span></div><div id="overview">${view === "matrix" ? matrix() : gap()}</div><div class="instrument-note"><strong>Task success ≠ evaluator approval</strong><p>The objective column uses a private reference check. Each judge follows its own rubric. A correct, concise answer can still fail a judge that rewards explanation.</p><p>Prediction is recorded before evaluation. Before/after changes are paired observations, not causal evidence.</p></div></section><section class="inspector" id="inspector" aria-label="Selected task detail">${inspector()}</section></main><footer class="footer"><div>${esc(data.id)}<br>Created ${esc(data.created_at)} / schema ${esc(data.schema_version)}</div><div>${resources.tokens ?? "Unknown"} tokens · ${resources.cost_usd == null ? "Unknown cost" : `$${fmt(resources.cost_usd, 6)}`} · ${fmt(resources.latency_ms, 1)} ms request/tool time<br>Portable local artifact / no external requests</div></footer></div>`;
    bind();
  }
  function bindSelection() {
    root.querySelectorAll("[data-select]").forEach((button) =>
      button.addEventListener("click", () => {
        selected = button.dataset.select;
        if (button.dataset.stage) stage = button.dataset.stage;
        render();
      }),
    );
  }
  function bind() {
    bindSelection();
    root.querySelectorAll("[data-view]").forEach((b) =>
      b.addEventListener("click", () => {
        view = b.dataset.view;
        render();
      }),
    );
    root.querySelectorAll("[data-attempt]").forEach((b) =>
      b.addEventListener("click", () => {
        stage = b.dataset.attempt;
        render();
      }),
    );
    root.querySelector("#filter").addEventListener("change", (e) => {
      filter = e.target.value;
      render();
    });
    root.querySelector("#search").addEventListener("input", (e) => {
      query = e.target.value;
      root.querySelector("#overview").innerHTML =
        view === "matrix" ? matrix() : gap();
      bindSelection();
    });
    root.querySelector("#event-filter")?.addEventListener("change", (e) => {
      eventFilter = e.target.value;
      render();
    });
    root.querySelector("#load-file").addEventListener("change", async (e) => {
      try {
        const file = e.target.files[0];
        if (!file) return;
        const next = JSON.parse(await file.text());
        if (
          next.schema_version !== "1.0" ||
          !Array.isArray(next.runs) ||
          !Array.isArray(next.tasks) ||
          !next.config?.evaluators ||
          !next.metrics?.stages ||
          !next.metrics?.resources ||
          !next.metrics?.pairs?.comparisons
        )
          throw new Error(
            "Choose a completed Agent Lab result.json (schema 1.0).",
          );
        for (const run of next.runs) {
          if (
            !run.task ||
            !Array.isArray(run.trace) ||
            !Array.isArray(run.verdicts) ||
            !Array.isArray(run.errors) ||
            !run.metrics ||
            !Array.isArray(run.task.tags)
          )
            throw new Error("The result contains an incomplete run record.");
          for (const v of run.verdicts)
            if (
              v.score != null &&
              (typeof v.score !== "number" || v.score < 0 || v.score > 1)
            )
              throw new Error("Invalid score in result file.");
        }
        const previous = data;
        try {
          data = next;
          selected = next.runs.find((r) => r.stage === "baseline")?.id;
          query = "";
          filter = "all";
          render();
        } catch (error) {
          data = previous;
          selected = previous.runs.find((r) => r.stage === "baseline")?.id;
          render();
          throw error;
        }
      } catch (error) {
        const notice = root.querySelector("#load-error");
        notice.textContent = `Could not open experiment: ${error.message}`;
        notice.classList.remove("hidden");
      }
    });
  }
  try {
    render();
  } catch (error) {
    root.textContent = `This experiment could not be displayed: ${error.message}. Inspect result.json with agentlab inspect.`;
  }
})();
