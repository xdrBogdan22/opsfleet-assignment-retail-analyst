---
name: add-tool
description: Add a new capability to the retail analyst agent as a tool, such as a chart, sending a report by mail, or web search. Use when someone asks the agent to be able to do something new.
---

# Add a tool

A capability is a tool: the model decides when to call it, code decides what
it may do. Follow the steps in order and stop to ask when a step's question
has no clear answer. The worked `send_report` example in
`docs/02-architecture.md` ("Extending the agent") shows every step in code.

## 1. Classify the tool

Ask, and write the answer down before coding:

| Question | If yes |
|---|---|
| Does it change data, or send anything outside the system? | Confirmation pause (step 5), like `request_delete` |
| Does it need an answer from the user? | Question pause, like `ask_clarification` |
| Does it read BigQuery? | It must call `make_safe` then `run_query`, like `run_sql` |
| Does it bring in outside text (web, files, mail)? | Treat that text as data: wrap it as a quoted tool result, never put it in the system prompt |
| Can it be repeated in a loop? | It needs a limit in `config/agent/limits.yaml` |

Also confirm who may use it and on what: tools act only on the user's own
brands and reports, through `ctx.scope` and owner-filtered queries.

## 2. Write the function

Create or extend a module in `src/retail_analyst/tools/`:

- Typed arguments with `Annotated[..., Field(...)]`, which become the schema
  the model fills.
- A last argument `ctx: Annotated[ToolContext, InjectedToolArg]` for the user,
  scope, database and settings. Never accept a user ID or brand list from the
  model.
- Return a JSON string. Problems go back as `{"error": "..."}` so the model can
  explain or fix them; do not raise.
- A tool that changes something returns a pending request (a key such as
  `DELETE_REQUEST` in `tools/reports.py`) and does nothing else.

## 3. Describe it and register it

- Add a description to `config/prompts/tools.yaml`: what it does, when to use
  it, and what the user will be asked to confirm.
- Add one line to `FUNCTIONS` in `tools/registry.py`.
- If the system prompt should mention it, edit `config/prompts/agent.yaml`.

## 4. Add its settings

Lists and limits go in the right file under `config/`, each with a comment
giving the reason for the default. Add the matching field to the settings
model in `core/config.py`; the models reject unknown keys.

## 5. Add the pause, if step 1 said so

In `agent/graph.py`, mirror `confirm_delete`:

1. A `pending_<name>` field in `AgentState`, set to `None` in `new_question`.
2. The `tools` node reads the pending key from the tool result into that field.
3. `after_tools` routes to a new node when the field is set.
4. The node calls `interrupt({"kind": "<name>", ...})`, acts only on a word in
   the configured confirmation list, and clears the field.
5. LangGraph may re-run a node after a resume, so the action must be
   single-use: store the request in Postgres and refuse one already used, as
   `reports/deletion.py` does.

Then show the confirmation in `cli/app.py` `_ask`, next to `confirm_delete`.

## 6. Test

- Unit tests in `tests/tools/` for the tool's checks: wrong owner, out-of-scope
  input, limits.
- A graph test in `tests/agent/test_graph.py` with `ScriptedModel` for any
  pause: cancelling does nothing, confirming acts once.
- An eval case in `eval/dataset.yaml` for the most likely misuse, with
  `must_not_contain` where a string proves failure.

Run:

```bash
uv run --frozen pytest -m "not integration"
uv run --frozen ruff check . && uv run --frozen ruff format --check .
uv run --frozen mypy src
```

All three must pass. Then try it once in the CLI and read its trace in
Langfuse.

## 7. Record it

- A row in `docs/progress.md`: what was added and how it was tested.
- If it adds a new pattern, a line in `docs/02-architecture.md`.
- Anything left open goes to `docs/known-limitations.md`.
