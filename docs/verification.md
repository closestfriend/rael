# First implementation verification

Verified locally on Python 3.11.16:

- 32 deterministic tests pass, including CLI execution of the full 12-task example.
- Ruff lint and formatting checks pass.
- Source and wheel distributions build successfully. A fresh environment installed
  the wheel and completed all 24 example attempts, including report generation.
- The explorer JavaScript passes `node --check`; its source is formatted with Prettier.
- The example produces 24 completed attempts, individually indexed in SQLite.
- Inspected JSONL traces match the corresponding run's embedded trace.
- The offline fixture's objective success changes from 7/12 to 11/12; five
  improvements and one regression. These are scripted demonstrations, not model
  performance measurements.
- Browser checks exercised matrix rendering, confidence-gap navigation, regression
  and tool filters, task selection, before/after switching, trace filtering,
  expansion of the actual calculator result `391`, and the empty search state.
- The browser reported no warnings/errors during those interaction checks. A
  full-page desktop screenshot was inspected at 1440px width with no page overflow.
  A later attempt to reconnect for a dedicated mobile check was blocked by browser
  URL policy; the 390px breakpoint remains unverified in-browser.
- An independent harness review found JSON boolean/number equality, uncontained
  grader exceptions and dropped malformed-tool response usage. Each issue was
  reproduced by a failing regression test and fixed before the full green suite.

No API key is configured in this execution environment. Live OpenAI calls remain
unverified; HTTP adapter tests use an injected transport, preserving real
serialization, response parsing and retry behavior without remote inference.

The report is generated from source assets inside the wheel. Open the generated
`results/<experiment-id>/report.html`, not the source `index.html` template.

## Implementation decisions

- A portable HTML/CSS/JavaScript explorer replaces a separate React build for this
  slice: same data, less setup. A richer application can consume `result.json` later.
- Existing sibling research projects were inspected for lineage but not copied or
  modified. RAEL is the new competition-neutral integration point.
- No automatic post-error retry repairs model JSON. Raw observable output remains
  in traces and the stage fails explicitly.
- Full MCP, automatic resume, external factory registration and human annotation
  editing are documented future work rather than simulated functionality.
