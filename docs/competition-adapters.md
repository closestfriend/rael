# Competition and environment adapters

Keep competition-specific parsing and rules out of `core`. A task adapter returns
validated `Task` objects; a provider translates model APIs into observable
`Completion` objects; a tool translates actions into JSON results. These are
separate responsibilities.

```python
from agentlab.core.models import Task

class ForecastingAdapter:
    def convert(self, record: dict) -> Task:
        return Task(
            id=record['id'],
            prompt=record['question'],
            context={'as_of': record['cutoff']},
            expected_output_type='probability',
            tags=['forecasting'],
            metadata={'source': 'competition-name'},
        )
```

For this MVP, serialize converted tasks to a JSON array and point the experiment
YAML's `tasks` field at it. Paths resolve relative to the YAML file. The built-in
JSON adapter rejects empty arrays and duplicate task IDs. No dynamic Python
imports or arbitrary execution are permitted through YAML.

To add a provider, implement `core/protocols.py::Provider`. It receives messages,
tool specs, purpose, structured-output preference and seed. It returns the public
assistant message, returned model ID and available usage. Register the provider
name in `ModelConfig` and `providers.make_provider`. Supply `provider_factory` to
`run_experiment` for Python integrations/tests. The core does not need vendor SDKs.

New agent implementations use the `Agent` protocol. In this version replace the
`ToolAgent` construction in the orchestrator to connect one; an external agent
factory registry is planned. New evaluators/tools similarly need explicit
registration. This small, visible wiring is intentional, rather than a plugin
discovery framework before the interfaces have stabilized.

## MCP preparation

`adapters/mcp.py` defines `MCPTransport.list_tools`, `MCPTransport.call_tool` and an
`MCPTool` wrapper. It is an interface, **not a functioning MCP client**. A transport
must implement negotiation, authentication, deadlines, cancellation and content
block translation. Register wrapped tools in the normal tool registry, then
allow them on individual tasks; the existing agent loop records calls/results.

Future filesystem, Python and coding environments require real isolation and
explicit budgets. The current calculator parses a bounded arithmetic AST and the
search stub reads only task-supplied references. Neither provides arbitrary code
execution or general network access.

## Nearby research lineage

The original directory was empty. Nearby Brie judging scripts and the Oyente
comparison app are potential future import sources. No sibling code, datasets,
credentials or private research records have been copied here. Use schema adapters
and behavioral equivalence tests before consolidating shared provider code.
