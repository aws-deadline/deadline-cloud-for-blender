# Timeouts

A Blender job runs three kinds of action on a worker: the step environment's enter and exit, and
one task per frame. This document specifies every time limit on those actions, which of them a
user can configure, and what happens when each one is reached.

Code: `template_filling.py` (`default_timeout_entries`, `BlenderSubmitterUISettings.timeouts`,
`BlenderSubmitterSettings.task_run_timeout_seconds`, `fill_job_template`, `_fill_step_template`),
`open_deadline_cloud_dialog.py` (`_ui_settings_to_submitter_settings`), `scene_settings_widget.py`
(`timeouts_box`), all under `src/deadline/blender_submitter/addons/deadline_cloud_blender_submitter/`.
Adaptor limits: `src/deadline/blender_adaptor/BlenderAdaptor/adaptor.py`. Tests:
`test/unit/deadline_submitter_for_blender/test_gui_submitter.py` and `test_submitter.py`.

## Problem

Open Job Description gives a task's `onRun` action no timeout unless the template sets one
([2023-09 `<Action>`](https://github.com/OpenJobDescription/openjd-specifications/wiki/2023-09-Template-Schemas)).
The adaptor fails a task only when Blender exits or prints a line it matches
([log-handling.md](../adaptor/log-handling.md)). A Blender process that stays alive and prints
nothing it recognizes, for example after a GPU error it does not match, keeps the task running
until someone cancels it. The worker running that task takes no other work in the meantime.

## The limits

| Limit | Value | Set in | Bounds | Configurable |
|-------|-------|--------|--------|--------------|
| Task run | Off, or the user's value | `onRun.timeout`, written by the submitter | `blender-openjd daemon run`: one frame | Yes, see [Task run timeout](#task-run-timeout) |
| Environment enter | 3720 s | `onEnter.timeout` in `default_blender_template.yaml` | `blender-openjd daemon start`: starting the adaptor and Blender, and loading the scene | No |
| Environment exit | 120 s | `onExit.timeout` in `default_blender_template.yaml` | `blender-openjd daemon stop`: the adaptor's `on_cleanup` | No |
| Cancel notify period | 120 s for `onRun`; 30 s for `onEnter` and `onExit` | Open Job Description defaults for `NOTIFY_THEN_TERMINATE`; the template does not set `notifyPeriodInSeconds` | The time between SIGTERM and SIGKILL when the worker cancels an action. On a timeout, only the Python runtime uses it; see [Task run](#task-run) | No |
| Adaptor server start | 30 s | `_SERVER_START_TIMEOUT_SECONDS` | The adaptor's internal server coming up | No |
| Blender start | 3600 s | `_BLENDER_START_TIMEOUT_SECONDS` | Blender starting and running its init actions. Raises `TimeoutError` | No |
| Blender close | 30 s | `_BLENDER_END_TIMEOUT_SECONDS` | Blender exiting after the close action in `on_cleanup` | No |
| Blender terminate grace | 60 s | `LoggingSubprocess.terminate` default in openjd-adaptor-runtime ([0.9.6 `_logging_subprocess.py#L197`](https://github.com/OpenJobDescription/openjd-adaptor-runtime-for-python/blob/0.9.6/src/openjd/adaptor_runtime/process/_logging_subprocess.py#L197)) | The time between SIGTERM and SIGKILL when `on_cleanup` terminates Blender | No |
| Adaptor server stop | 30 s | `_SERVER_END_TIMEOUT_SECONDS` | Joining the adaptor's server thread in `on_cleanup` | No |

The Blender start limit (3600 s) runs inside the environment enter limit (3720 s). A slow scene load
therefore fails with the adaptor's `TimeoutError`, which names the cause, before the worker's own
timeout cancels the action.

## Task run timeout

### Submitter dialog

The "Job-specific settings" tab shows a Timeouts box (`TimeoutTableWidget` from deadline-cloud)
with one row, `Task Run`.

| Property | Value |
|----------|-------|
| Default | Off (`is_activated=False`) |
| Pre-filled value | 2 days (`DEFAULT_TASK_RUN_TIMEOUT_SECONDS`, 172800 s), used when the user checks the row |
| Unit | Days, hours and minutes, so the smallest value is 1 minute |
| Warning | While the row is unchecked, the widget shows "Warning: Without a specified timeout, tasks may run indefinitely if issues occur." |

When the user submits or exports a bundle, `_ui_settings_to_submitter_settings` calls
`TimeoutTableEntries.validate_entries`. A checked row set to 0 raises `NonValidInputError`, which
the dialog shows as "Non valid inputs detected":

```
The following timeout value(s) must be greater than 0:
Task Run

Please configure these value(s) in the 'Job specific settings' tab.
```

A checked row maps to `task_run_timeout_seconds = <seconds>`. An unchecked row maps to `0`.

### Sticky settings

`timeouts` is a sticky field, saved in `<scene>.deadline_render_settings.json` as:

```json
"timeouts": {"Task Run": {"is_activated": true, "seconds": 5400}}
```

The tooltip is not saved. On load:

1. The saved rows update the existing rows in place (`update_from_sticky_settings`), so a row added
   in a later version keeps its default.
2. A row name that is not in the table is ignored.
3. `_valid_timeout_sticky_entries` drops an entry whose `is_activated` is not a boolean, whose
   `seconds` is not a whole number 0 or greater, or that is not an object. If `timeouts` itself is
   not an object, every row keeps its default. Other sticky fields still load.
4. A file written before this setting existed has no `timeouts` key, so the row stays off.

### API submissions

`BlenderSubmitterSettings.task_run_timeout_seconds` is the seconds for every step's `onRun`. The
default is `0`, meaning no timeout, so an API submission behaves like the dialog's default.

`fill_job_template` raises `DeadlineOperationError` for a value that is negative, not an `int`, or
a `bool`:

```
The task run timeout must be a whole number of seconds, 0 or greater: <value!r>
```

### Template output

`fill_job_template` builds one step per view layer. For a value above 0, each step gets:

```yaml
script:
  actions:
    onRun:
      command: blender-openjd
      ...
      cancelation:
        mode: NOTIFY_THEN_TERMINATE
      timeout: 3600
```

For 0 there is no `timeout` key. The environment's `onEnter` and `onExit` timeouts are never
changed.

### Why a literal number

Without an extension, a 2023-09 template accepts only a positive integer for `timeout`. Making it a
job parameter would need `FEATURE_BUNDLE_1` (a `{{Param.X}}` string), and expressing "no timeout"
as 0 would also need `EXPR`. Every farm and worker that runs the job would have to support those
extensions. Writing the number into the template at submission works on every worker, and matches
the Maya, Cinema 4D, Nuke and 3ds Max submitters. The cost is that the value is fixed when the job
is submitted.

## When a limit is reached

### Task run

What the worker does at the time limit depends on the session runtime it uses. The worker agent
runs a session on the Python runtime
([openjd-sessions-for-python](https://github.com/OpenJobDescription/openjd-sessions-for-python))
or the Rust runtime ([openjd-rs](https://github.com/OpenJobDescription/openjd-rs) `openjd-sessions`).
Since worker agent 0.33.2, the default `session_runtime = "service-selected"` uses the Python runtime
unless the service sends a `runtimeHint` of `rust`.

Blender does not run under the `onRun` process. `daemon start` (the environment enter) launches the
adaptor daemon with `start_new_session=True`
([0.9.6 `frontend_runner.py#L162`](https://github.com/OpenJobDescription/openjd-adaptor-runtime-for-python/blob/0.9.6/src/openjd/adaptor_runtime/_background/frontend_runner.py#L162)),
and Blender is the daemon's child. `daemon run` is a frontend that asks the daemon to render a frame.
A signal to `daemon run`'s process group therefore does not reach the daemon or Blender.

**Python runtime** (openjd-sessions 0.14.0):

1. At the limit, `_on_timelimit` calls `cancel()`, which uses the action's cancelation method
   ([`_runner_base.py`](https://github.com/OpenJobDescription/openjd-sessions-for-python/blob/0.14.0/src/openjd/sessions/_runner_base.py)).
   For `NOTIFY_THEN_TERMINATE` with no `notifyPeriodInSeconds`, the step runner uses
   `TASK_RUN_DEFAULT_NOTIFY_PERIOD_SECONDS`: SIGTERM to `daemon run`, then SIGKILL 120 s later if it
   is still running.
2. The `daemon run` frontend handles SIGTERM by sending `PUT /cancel` to the daemon
   ([0.9.6 `frontend_runner.py`, `_sigint_handler` and `cancel`](https://github.com/OpenJobDescription/openjd-adaptor-runtime-for-python/blob/0.9.6/src/openjd/adaptor_runtime/_background/frontend_runner.py)).
3. The adaptor's `on_cancel` terminates Blender with no grace period (`terminate(grace_time_s=0)`).
4. The task ends with the Timeout state. The environment exit (`daemon stop`) runs `on_cleanup`,
   which finds Blender already stopped.

**Rust runtime** (openjd-rs `openjd-sessions`):

1. At the limit, the runtime sends SIGKILL to `daemon run`'s process group at once. It does not use
   the action's cancelation method or notify period
   ([`crates/openjd-sessions/src/subprocess.rs`](https://github.com/OpenJobDescription/openjd-rs/blob/main/crates/openjd-sessions/src/subprocess.rs),
   "Action timed out, sending SIGKILL to process group"; `specs/sessions/subprocess.md`).
2. SIGKILL cannot be handled, so the frontend sends no cancel. The daemon and Blender keep running.
3. The task ends with the Timeout state. Blender is stopped only by the environment exit:
   `on_cleanup` queues the close action, and a hung Blender may not run it. After 30 s the adaptor
   terminates Blender (SIGTERM, then SIGKILL after 60 s).

**What is verified.** The Python steps 1 and 2 and the Rust step 1 are read from the code at the
versions linked. Python step 3 is tested against real Blender by
`test_adaptor_cancel_closes_blender` (`test/integ/test_adaptor_lifecycle.py`), which calls
`on_cancel` directly. Python step 4 and Rust steps 2 and 3 are not tested, and no test runs a job
until a limit is reached. On the Rust runtime, whether `daemon stop` still works while the daemon is
in the middle of the canceled frame has not been checked.

### Environment enter

The worker cancels `daemon start`: on the Python runtime with a 30 s notify period, on the Rust
runtime with an immediate SIGKILL. The session fails before any task runs. In practice the
adaptor's 3600 s Blender start limit fires first.

### Environment exit

`on_cleanup` queues the close action and waits up to 30 s for Blender to exit. If Blender is still
running, it terminates Blender (SIGTERM, then SIGKILL after 60 s), then waits up to 30 s for the
server thread. If `daemon stop` is still running at 120 s, the worker cancels it: on the Python
runtime with a 30 s notify period, on the Rust runtime with an immediate SIGKILL. Either way the
signal goes to `daemon stop`, not to the daemon that runs Blender.

## Known gaps

| Gap | Effect |
|-----|--------|
| The task run timeout is off by default | A job that never sets it can still hang until someone cancels the task |
| The value is written at submission | A job's timeout cannot change after it is submitted. Templates that do not come from this submitter, including customized copies of its template, get no timeout from this feature |
| On the Rust runtime, a task run timeout sends SIGKILL to `daemon run` only | The adaptor gets no cancel, and a hung Blender keeps running until the environment exit's cleanup terminates it, up to about 90 s later. See [Task run](#task-run) |
| `on_cleanup` can take up to 30 + 60 + 30 = 120 s, the same as the `onExit` limit | If Blender ignores the close action, the worker may cancel `daemon stop` before cleanup ends, and the session logs a failed exit. That cancel reaches `daemon stop`, not the daemon, so whether Blender is still stopped then depends on the worker ending the session's processes. Not checked |
| No test runs a job until a limit is reached | Only `on_cancel` is tested. The rest of the paths in [Task run](#task-run) are read from code |
| The dialog's error names the "Job specific settings" tab; the tab is labelled "Job-specific settings" | Cosmetic. The text comes from deadline-cloud |

## Tests

| Rule | Test |
|------|------|
| Off by default; 2 days pre-filled | `test_ui_settings_default_task_run_timeout`, `test_blender_submitter_settings_default_task_run_timeout`, `test_fill_job_template_has_no_task_run_timeout_by_default` |
| The value is written into every step; `onEnter` and `onExit` unchanged | `test_fill_job_template_sets_custom_task_run_timeout_on_every_step` |
| 0 means no `timeout` key | `test_fill_job_template_zero_task_run_timeout_means_no_timeout` |
| Invalid API values are rejected | `test_fill_job_template_rejects_invalid_task_run_timeout` |
| UI row to API value, and the zero-value error | `test_ui_settings_adapter_maps_task_run_timeout`, `test_ui_settings_adapter_rejects_enabled_zero_timeout` |
| Sticky settings save, load, and fall back | `test_sticky_settings_round_trip_task_run_timeout`, `test_sticky_settings_without_timeouts_keep_default`, `test_sticky_settings_malformed_timeouts_keep_default`, `test_sticky_settings_ignore_unknown_timeout_rows`, `test_ui_settings_timeouts_are_not_shared_between_instances` |
| Full template, including the absent `onRun` timeout | `test_fill_job_template` and the expected templates under `test/integ/test_scripts/*/expected_job_bundle/` |
| In real Blender: checking the row and setting 1 h 30 min in the Timeouts box writes `timeout: 5400` into every step's `onRun`, leaves `onEnter` and `onExit` unchanged, and saves the row in the sticky settings | `test_task_run_timeout_submitter` in `test/integ/test_blender_submitters.py`, with `test/integ/test_scripts/task_run_timeout_test/` |
| `on_cancel` stops Blender | `test_adaptor_cancel_closes_blender` in `test/integ/test_adaptor_lifecycle.py` |

## Changing this behavior

1. Update this document in the same commit as the code.
2. A new configurable timeout is a new row in `default_timeout_entries`, with code in
   `_ui_settings_to_submitter_settings` and `fill_job_template` that writes it. Old sticky files
   must keep loading.
3. Changing a template default changes `test_fill_job_template` and the integration expected
   templates. Update both.

## References

- [Open Job Description 2023-09 template schemas](https://github.com/OpenJobDescription/openjd-specifications/wiki/2023-09-Template-Schemas):
  `<Action>` `timeout` and its defaults, and `<CancelationMethodNotifyThenTerminate>`.
- deadline-cloud 0.60.4:
  [`ui/dataclasses/timeouts.py`](https://github.com/aws-deadline/deadline-cloud/blob/0.60.4/src/deadline/client/ui/dataclasses/timeouts.py),
  [`ui/widgets/job_timeouts_widget.py`](https://github.com/aws-deadline/deadline-cloud/blob/0.60.4/src/deadline/client/ui/widgets/job_timeouts_widget.py).
- openjd-adaptor-runtime-for-python 0.9.6:
  https://github.com/OpenJobDescription/openjd-adaptor-runtime-for-python/tree/0.9.6
- openjd-sessions-for-python 0.14.0, the version worker agent 0.33 pins:
  https://github.com/OpenJobDescription/openjd-sessions-for-python/tree/0.14.0
- openjd-rs `openjd-sessions`: https://github.com/OpenJobDescription/openjd-rs, `specs/sessions/`.
- deadline-cloud-worker-agent: https://github.com/aws-deadline/deadline-cloud-worker-agent,
  `src/deadline_worker_agent/sessions/runtime/_select.py`.
