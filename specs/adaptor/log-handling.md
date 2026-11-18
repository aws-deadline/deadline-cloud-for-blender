# Blender Log Handling

The adaptor starts Blender as a child process and learns what Blender is doing only from what
Blender prints. This document specifies how the adaptor reads that output, every pattern it
matches, what each match does, and which code prints the matched text in each Blender release
from 4.0 to 5.3.

Code: `src/deadline/blender_adaptor/BlenderAdaptor/adaptor.py` (`_get_regex_callbacks`, the
`_handle_*` callbacks, `on_start`, `on_run`). Tests:
`test/unit/deadline_adaptor_for_blender/test_adaptor.py`.

## Problem

Nothing outside the Blender process can query it for a render's progress or failure. Its only
signals are its text output and its exit code, so the adaptor treats specific output lines as
events. The text of those lines comes from Blender, the Cycles and EEVEE engines, NVIDIA's OptiX
library, or this repo's Blender client, and it changes between Blender releases. Each pattern below
records where its text comes from, so that a change in Blender can be traced to the pattern it
breaks.

## Reading the output

`_start_blender_client` starts Blender with
`--background --python-exit-code 1 --python <blender_client.py> --python-use-system-env` through
openjd-adaptor-runtime's `LoggingSubprocess`. Runtime links are pinned to 0.9.6; `pyproject.toml`
accepts `>= 0.7, < 0.10`.

1. stdout and stderr are separate pipes. Both are decoded as UTF-8 with `errors="backslashreplace"`
   ([_logging_subprocess.py#L77](https://github.com/OpenJobDescription/openjd-adaptor-runtime-for-python/blob/0.9.6/src/openjd/adaptor_runtime/process/_logging_subprocess.py#L77)),
   so an undecodable byte cannot stop the reader.
2. Each stream has a reader thread. It splits the output into lines and removes the line ending
   ([_stream_logger.py#L53](https://github.com/OpenJobDescription/openjd-adaptor-runtime-for-python/blob/0.9.6/src/openjd/adaptor_runtime/process/_stream_logger.py#L53)).
   Each line is one event, so a multi-line Blender message arrives as several lines.
3. Every line is logged, whether or not it matches, at level `STDOUT` or `STDERR`
   ([_logging.py#L6](https://github.com/OpenJobDescription/openjd-adaptor-runtime-for-python/blob/0.9.6/src/openjd/adaptor_runtime/process/_logging.py#L6),
   [#L9](https://github.com/OpenJobDescription/openjd-adaptor-runtime-for-python/blob/0.9.6/src/openjd/adaptor_runtime/process/_logging.py#L9)).
   The session log shows `STDOUT: <line>`
   ([_entrypoint.py#L182](https://github.com/OpenJobDescription/openjd-adaptor-runtime-for-python/blob/0.9.6/src/openjd/adaptor_runtime/_entrypoint.py#L182)).
   When the adaptor runs as a daemon, the line appears as `ADAPTOR_OUTPUT: STDOUT: <line>`
   ([frontend_runner.py#L293](https://github.com/OpenJobDescription/openjd-adaptor-runtime-for-python/blob/0.9.6/src/openjd/adaptor_runtime/_background/frontend_runner.py#L293)).
4. One `RegexHandler` receives the lines of both streams
   ([_logging_subprocess.py#L124](https://github.com/OpenJobDescription/openjd-adaptor-runtime-for-python/blob/0.9.6/src/openjd/adaptor_runtime/process/_logging_subprocess.py#L124),
   [#L126](https://github.com/OpenJobDescription/openjd-adaptor-runtime-for-python/blob/0.9.6/src/openjd/adaptor_runtime/process/_logging_subprocess.py#L126)).
   For each line it tries the callbacks in list order and calls every callback that matches; no
   callback stops the others
   ([_regex_callback_handler.py#L104](https://github.com/OpenJobDescription/openjd-adaptor-runtime-for-python/blob/0.9.6/src/openjd/adaptor_runtime/app_handlers/_regex_callback_handler.py#L104)).
   A callback matches when any of its patterns matches under `re.search`
   ([#L63](https://github.com/OpenJobDescription/openjd-adaptor-runtime-for-python/blob/0.9.6/src/openjd/adaptor_runtime/app_handlers/_regex_callback_handler.py#L63)),
   so an unanchored pattern matches anywhere in the line.
5. Callbacks run on the reader threads. A callback that fails the task does not raise. It stores
   the exception in `_exc_info`, and the main thread raises it (see
   [How a failure reaches the task](#how-a-failure-reaches-the-task)).

### Why one handler for both streams

Blender 4.x prints Cycles errors on stderr, while Blender 5 prints them on stdout. Python tracebacks
go to stderr, and the client's own lines go to stdout. With one handler on both streams, a pattern
works whichever stream a Blender release uses.

## Patterns

`_get_regex_callbacks` builds this list once, when Blender starts:

| # | Callback | Pattern | Registered | Effect |
|---|----------|---------|------------|--------|
| 1 | `_handle_complete` | `BlenderClient: Finished Rendering Frame [0-9]+` | Always | The frame is done: progress 100, and `on_run` stops waiting |
| 2 | `_handle_progress` | `^Fra:.*Sample\s(\d+)\/(\d+)$` (Cycles), `^Fra:.*Rendering\s(\d+)\s/\s(\d+)\ssamples$` (EEVEE) | Always | Progress becomes ⌊N ÷ M × 100⌋ |
| 3 | `_handle_error` | `.*Exception:.*\|.*Error:.*\|.*Warning.*` | Only when init-data has `strict_error_checking: true` | Fails the task |
| 4 | `_handle_version` | `BlenderClient: Blender Version ([0-9]+.[0-9]+.[0-9]+)` | Always | Records the Blender version for telemetry |
| 5 | `_handle_out_of_memory` | `_OUT_OF_MEMORY_REGEXES` | Always | Fails the task |

Keep this order: the unit tests read the progress callback at index 1. A line that matches no
pattern is only logged. The adaptor has no progress pattern for Workbench, so a Workbench frame
goes from 0 straight to 100.

### 1. Frame complete

**Text source.** This repo's client, not Blender. `DefaultBlenderHandler.start_render` in
`src/deadline/blender_adaptor/BlenderClient/render_handlers/default_blender_handler.py` prints
`BlenderClient: Finished Rendering Frame <frame>` after `bpy.ops.render.render` returns. The Cycles
and Workbench handlers inherit `start_render`, so the text is the same for every engine and every
Blender release.

**Behavior.** `_handle_complete` sets `_is_rendering` to false and reports progress 100. The wait
in `on_run` ends, and the rules in [Process exit](#process-exit) apply.

### 2. Render progress

**Behavior.** `_handle_progress` reports `int(N / M * 100)`. Both patterns need a line that starts
with `Fra:` and ends with the sample count.

**Text source, Blender 4.x.** In background mode, Blender installs `stats_background`
([v4.0.0 pipeline.cc#L559](https://github.com/blender/blender/blob/v4.0.0/source/blender/render/intern/pipeline.cc#L559)).
It prints the engine's status on stdout as `Fra:%d Mem:%.2fM (Peak %.2fM) | Time:%s | <info>`:

| Release | Stats line |
|---------|------------|
| 4.0 | [pipeline.cc#L210](https://github.com/blender/blender/blob/v4.0.0/source/blender/render/intern/pipeline.cc#L210), printed in pieces up to [#L217](https://github.com/blender/blender/blob/v4.0.0/source/blender/render/intern/pipeline.cc#L217) |
| 4.1 | [pipeline.cc#L213](https://github.com/blender/blender/blob/v4.1.0/source/blender/render/intern/pipeline.cc#L213), printed in pieces up to [#L220](https://github.com/blender/blender/blob/v4.1.0/source/blender/render/intern/pipeline.cc#L220) |
| 4.2 | [pipeline.cc#L217](https://github.com/blender/blender/blob/v4.2.0/source/blender/render/intern/pipeline.cc#L217), printed at [#L223](https://github.com/blender/blender/blob/v4.2.0/source/blender/render/intern/pipeline.cc#L223) |
| 4.3 | [pipeline.cc#L218](https://github.com/blender/blender/blob/v4.3.0/source/blender/render/intern/pipeline.cc#L218), printed at [#L226](https://github.com/blender/blender/blob/v4.3.0/source/blender/render/intern/pipeline.cc#L226) |
| 4.4 | [pipeline.cc#L213](https://github.com/blender/blender/blob/v4.4.0/source/blender/render/intern/pipeline.cc#L213), printed at [#L221](https://github.com/blender/blender/blob/v4.4.0/source/blender/render/intern/pipeline.cc#L221) |
| 4.5 | [pipeline.cc#L216](https://github.com/blender/blender/blob/v4.5.0/source/blender/render/intern/pipeline.cc#L216), printed at [#L224](https://github.com/blender/blender/blob/v4.5.0/source/blender/render/intern/pipeline.cc#L224) |

- **Cycles.** `BlenderSession::update_status_progress` builds `<info>`
  ([4.0 #L998](https://github.com/blender/blender/blob/v4.0.0/intern/cycles/blender/session.cpp#L998),
  [4.1 #L1033](https://github.com/blender/blender/blob/v4.1.0/intern/cycles/blender/session.cpp#L1033),
  [4.2–4.5 #L1039](https://github.com/blender/blender/blob/v4.5.0/intern/cycles/blender/session.cpp#L1039)).
  It ends with `Sample %d/%d` from `Session::update_status_time`
  ([4.0 #L710](https://github.com/blender/blender/blob/v4.0.0/intern/cycles/session/session.cpp#L710),
  [4.2 #L724](https://github.com/blender/blender/blob/v4.2.0/intern/cycles/session/session.cpp#L724),
  [4.4 #L736](https://github.com/blender/blender/blob/v4.4.0/intern/cycles/session/session.cpp#L736),
  [4.5 #L731](https://github.com/blender/blender/blob/v4.5.0/intern/cycles/session/session.cpp#L731)).
  When Cycles appends a device status in parentheses
  ([4.5 #L737](https://github.com/blender/blender/blob/v4.5.0/intern/cycles/session/session.cpp#L737)),
  the line no longer ends with the count, and it updates nothing.
- **EEVEE.** The status is `Rendering N / M samples`:
  - Legacy EEVEE in 4.0 and 4.1 prints it every 25 samples and on the last one
    ([4.0 eevee_render.cc#L590](https://github.com/blender/blender/blob/v4.0.0/source/blender/draw/engines/eevee/eevee_render.cc#L590),
    [4.1 #L591](https://github.com/blender/blender/blob/v4.1.0/source/blender/draw/engines/eevee/eevee_render.cc#L591)).
  - EEVEE Next in 4.2.0 prints no per-sample status
    ([eevee_instance.cc#L519](https://github.com/blender/blender/blob/v4.2.0/source/blender/draw/engines/eevee_next/eevee_instance.cc#L519)),
    so 4.2.0 EEVEE renders report no progress.
  - From 4.2.1, EEVEE prints it at sample 1, every 25th sample and the last one
    ([4.2.1 eevee_next/eevee_instance.cc#L527](https://github.com/blender/blender/blob/v4.2.1/source/blender/draw/engines/eevee_next/eevee_instance.cc#L527),
    [4.3 #L517](https://github.com/blender/blender/blob/v4.3.0/source/blender/draw/engines/eevee_next/eevee_instance.cc#L517),
    [4.4 #L527](https://github.com/blender/blender/blob/v4.4.0/source/blender/draw/engines/eevee_next/eevee_instance.cc#L527),
    [4.5 eevee/eevee_instance.cc#L652](https://github.com/blender/blender/blob/v4.5.0/source/blender/draw/engines/eevee/eevee_instance.cc#L652)).

**Text source, Blender 5.x.** `stats_background` logs the status through CLOG log type `render`
([#L104](https://github.com/blender/blender/blob/v5.0.0/source/blender/render/intern/pipeline.cc#L104))
at INFO level, and only when INFO is enabled for that type:

| Release | Stats line |
|---------|------------|
| 5.0.0 | [pipeline.cc#L201](https://github.com/blender/blender/blob/v5.0.0/source/blender/render/intern/pipeline.cc#L201), [#L203](https://github.com/blender/blender/blob/v5.0.0/source/blender/render/intern/pipeline.cc#L203): the status only |
| 5.0.1 | [pipeline.cc#L203](https://github.com/blender/blender/blob/v5.0.1/source/blender/render/intern/pipeline.cc#L203): `Fra: %d \| %s` |
| 5.1 | [pipeline.cc#L202](https://github.com/blender/blender/blob/v5.1.0/source/blender/render/intern/pipeline.cc#L202) |
| 5.2 | [pipeline.cc#L210](https://github.com/blender/blender/blob/v5.2.0/source/blender/render/intern/pipeline.cc#L210), background mode only ([#L208](https://github.com/blender/blender/blob/v5.2.0/source/blender/render/intern/pipeline.cc#L208)) |
| 5.3 | [pipeline.cc#L211](https://github.com/blender/blender/blob/v5.3.0/source/blender/render/intern/pipeline.cc#L211) |

CLOG's default level is WARN
([clog.cc#L825](https://github.com/blender/blender/blob/v5.0.0/intern/clog/clog.cc#L825)). Only
command-line renders add the `render.*` INFO filter
([creator_args.cc#L2306](https://github.com/blender/blender/blob/v5.0.0/source/creator/creator_args.cc#L2306)),
from the `-f` and `-a` handlers
([#L2324](https://github.com/blender/blender/blob/v5.0.0/source/creator/creator_args.cc#L2324),
[#L2380](https://github.com/blender/blender/blob/v5.0.0/source/creator/creator_args.cc#L2380)).
The adaptor renders through `bpy.ops.render.render`, so Blender 5 prints no status line, and
**the progress patterns never match on Blender 5**. A frame's progress stays at 0 until the frame
completes. If INFO were enabled, the line would still start with the CLOG prefix, which `^Fra:`
rejects. Cycles and EEVEE still build the same text: Cycles `Sample %d/%d`
([5.0 #L733](https://github.com/blender/blender/blob/v5.0.0/intern/cycles/session/session.cpp#L733),
[5.3 #L766](https://github.com/blender/blender/blob/v5.3.0/intern/cycles/session/session.cpp#L766)),
and EEVEE `Rendering N / M samples`
([5.0 #L657](https://github.com/blender/blender/blob/v5.0.0/source/blender/draw/engines/eevee/eevee_instance.cc#L657),
[5.3 #L705](https://github.com/blender/blender/blob/v5.3.0/source/blender/draw/engines/eevee/eevee_instance.cc#L705)).

### 3. Strict error checking

**Registration.** Only when init-data sets `strict_error_checking: true`. The submitter's default
job template defines a `StrictErrorChecking` parameter but does not pass it to init-data, so jobs
from the default template never register this callback.

**Behavior.** `_handle_error` sets `_exc_info` to
`RuntimeError("Blender Encountered an Error: <line>")`, replacing any earlier error. The task fails
at the next check. `.*Warning.*` matches the word anywhere in a line, so a warning also fails the
task.

**Text sources.**

- **Python.** Exceptions and warnings, in CPython's format: the last line of a traceback
  (`RuntimeError: ...`, `Exception: ...`) and `<Category>Warning:` lines.
- **Blender 4.x reports.** These print as `Error: <message>` and `Warning: <message>`
  ([4.0 report.cc#L92](https://github.com/blender/blender/blob/v4.0.0/source/blender/blenkernel/intern/report.cc#L92),
  with the type names at [#L38](https://github.com/blender/blender/blob/v4.0.0/source/blender/blenkernel/intern/report.cc#L38)
  and [#L40](https://github.com/blender/blender/blob/v4.0.0/source/blender/blenkernel/intern/report.cc#L40);
  [4.5 #L133](https://github.com/blender/blender/blob/v4.5.0/source/blender/blenkernel/intern/report.cc#L133)).
  The client runs the render as an operator from Python. Such an operator holds its reports
  ([bpy_operator.cc#L238](https://github.com/blender/blender/blob/v4.0.0/source/blender/python/intern/bpy_operator.cc#L238))
  and raises the errors as a Python `RuntimeError` when it returns
  ([#L257](https://github.com/blender/blender/blob/v4.0.0/source/blender/python/intern/bpy_operator.cc#L257)).
- **Blender 5.x.** CLOG writes severities in capitals, `ERROR` and `WARNING`
  ([clog.cc#L327](https://github.com/blender/blender/blob/v5.0.0/intern/clog/clog.cc#L327),
  [#L329](https://github.com/blender/blender/blob/v5.0.0/intern/clog/clog.cc#L329)), and reports
  go through CLOG log type `reports`
  ([report.cc#L31](https://github.com/blender/blender/blob/v5.0.0/source/blender/blenkernel/intern/report.cc#L31),
  [#L160](https://github.com/blender/blender/blob/v5.0.0/source/blender/blenkernel/intern/report.cc#L160)).
  The case-sensitive pattern matches neither. On Blender 5, strict mode fails only on Python
  exceptions and warnings, and on text that itself contains `Error:` or `Warning`. No line of the
  observed Blender 5.0 failure in [Example](#example-blender-50-gpu-out-of-memory) matches it.

### 4. Blender version

**Text source.** This repo's `BlenderClient.__init__`, in
`src/deadline/blender_adaptor/BlenderClient/blender_client.py`, prints
`BlenderClient: Blender Version <bpy.app.version_string>` when the client starts. `bpy.app`
exposes Blender's version string
([4.0 bpy_app.cc#L154](https://github.com/blender/blender/blob/v4.0.0/source/blender/python/intern/bpy_app.cc#L154),
[5.0 #L223](https://github.com/blender/blender/blob/v5.0.0/source/blender/python/intern/bpy_app.cc#L223)).
Blender builds the string as `%d.%01d.%d%s` in 4.0–4.2
([4.0 blender.cc#L119](https://github.com/blender/blender/blob/v4.0.0/source/blender/blenkernel/intern/blender.cc#L119),
[4.2 #L117](https://github.com/blender/blender/blob/v4.2.0/source/blender/blenkernel/intern/blender.cc#L117)).
From 4.3 it uses `%d.%01d.%d%s%s`, which adds an ` LTS` suffix
([4.3 #L124](https://github.com/blender/blender/blob/v4.3.0/source/blender/blenkernel/intern/blender.cc#L124),
[5.0 #L131](https://github.com/blender/blender/blob/v5.0.0/source/blender/blenkernel/intern/blender.cc#L131),
[5.3 #L132](https://github.com/blender/blender/blob/v5.3.0/source/blender/blenkernel/intern/blender.cc#L132)).

**Behavior.** `_handle_version` keeps `X.Y.Z` as the telemetry `blender-version`. The `.` in the
pattern is unescaped and matches any character. That is harmless, because the client always prints
dots.

### 5. Out of memory

**Behavior.** This callback is always registered. On the first match, `_handle_out_of_memory` sets
`_exc_info` to `RuntimeError("Blender ran out of memory: <line>")`, unless an error is already set.
The task then fails at the next check, without waiting for Blender to exit.

**Why it fails the task.** Cycles stops rendering after any device error
([4.0 session.cpp#L182](https://github.com/blender/blender/blob/v4.0.0/intern/cycles/session/session.cpp#L182),
[5.3 #L203](https://github.com/blender/blender/blob/v5.3.0/intern/cycles/session/session.cpp#L203)).
The failed-allocation message comes with `Progress::set_error`, which cancels the render
([4.0 progress.h#L118](https://github.com/blender/blender/blob/v4.0.0/intern/cycles/util/progress.h#L118),
[5.3 #L103](https://github.com/blender/blender/blob/v5.3.0/intern/cycles/util/progress.h#L103)).
So a render that printed one of these messages cannot succeed. The OptiX message is the exception:
Cycles only logs it, and whether OptiX recovers from it is not known. In the
[observed case](#example-blender-50-gpu-out-of-memory) an OptiX launch error followed it. After any of these messages Blender can stop rendering without exiting,
and waiting for the exit would never end.

**Matching rules.**

1. The exact message text, case-sensitive. Each message is a fixed string in Cycles, cuew, hipew
   or OptiX.
2. The message must start where Blender starts an error message (`_ERROR_START`). That is the start
   of the line (Blender 4.x prints these bare), after `| ERROR ` (Blender 5's log), after `Error: `
   (a report or a Python exception), or after `] ` (a Blender 4.x glog line). The CUDA error name
   may also end the line in parentheses. Blender prints scene, object and file names in ordinary
   lines (`Fra: … | Synchronizing object | <name>`, `Saved: '<path>'`), and the anchor keeps those
   names from failing a render.
3. Out-of-memory messages only.

| Pattern | Message | Printed by |
|---------|---------|------------|
| `_ERROR_START + "System is out of GPU (?:and shared host )?memory"` | `System is out of GPU memory`, `System is out of GPU and shared host memory` | `GPUDevice::generic_alloc` (CUDA, OptiX, HIP, oneAPI) and Metal, when an allocation does not fit |
| `_ERROR_START + "Out of memory"`, `\(Out of memory\)$` | `Out of memory in <call> (<file>:<line>)`, `Out of memory in CUDA queue <op> (<kernels>)`, `Failed to … (Out of memory)` | The CUDA or HIP error name for `CUDA_ERROR_OUT_OF_MEMORY` and `hipErrorOutOfMemory` (cuew, hipew), in Cycles' driver-call checks |
| `_ERROR_START + "Out of memory"` | `Out of memory` (5.x) | `MEM_GUARDED_CALL`, when an allocation throws `std::bad_alloc` during scene upload or BVH build |
| `Error: run out of memory!` | `Error: run out of memory!` (4.x) | The same `MEM_GUARDED_CALL` in Blender 4.x |
| `_ERROR_START + "cblCudaReconfigureLocalMemory failed with out of memory"` | `cblCudaReconfigureLocalMemory failed with out of memory` | NVIDIA OptiX. The string is not in Blender's source; Cycles relays OptiX error messages through its OptiX log callback |

Each series below is pinned at its `.0` tag. All 64 tags from v4.0.0 to v5.3.0 were checked: the
text is identical in every tag, and patch releases only move lines (listed after the table).

| Release | `System is out of GPU memory` | `System is out of GPU and shared host memory` | `Out of memory` (CUDA / HIP error name) | Failed allocation | OptiX relay | Printed by |
|---|---|---|---|---|---|---|
| 4.0 (`v4.0.0`) | [device.cpp#L697](https://github.com/blender/blender/blob/v4.0.0/intern/cycles/device/device.cpp#L697), [metal#L730](https://github.com/blender/blender/blob/v4.0.0/intern/cycles/device/metal/device_impl.mm#L730) | [device.cpp#L701](https://github.com/blender/blender/blob/v4.0.0/intern/cycles/device/device.cpp#L701) | [cuew.c#L710](https://github.com/blender/blender/blob/v4.0.0/extern/cuew/src/cuew.c#L710), [hipew.c#L433](https://github.com/blender/blender/blob/v4.0.0/extern/hipew/src/hipew.c#L433); formats [util.h#L36](https://github.com/blender/blender/blob/v4.0.0/intern/cycles/device/cuda/util.h#L36), [queue.cpp#L214](https://github.com/blender/blender/blob/v4.0.0/intern/cycles/device/cuda/queue.cpp#L214) | `Error: run out of memory!` [guarded_allocator.h#L159](https://github.com/blender/blender/blob/v4.0.0/intern/cycles/util/guarded_allocator.h#L159) | [device_impl.cpp#L75](https://github.com/blender/blender/blob/v4.0.0/intern/cycles/device/optix/device_impl.cpp#L75), only with `--debug-cycles`/`--verbose` | bare line on stderr: [device.h#L171](https://github.com/blender/blender/blob/v4.0.0/intern/cycles/device/device.h#L171) |
| 4.1 (`v4.1.0`) | [device.cpp#L724](https://github.com/blender/blender/blob/v4.1.0/intern/cycles/device/device.cpp#L724), [metal#L735](https://github.com/blender/blender/blob/v4.1.0/intern/cycles/device/metal/device_impl.mm#L735) | [device.cpp#L728](https://github.com/blender/blender/blob/v4.1.0/intern/cycles/device/device.cpp#L728) | [cuew.c#L710](https://github.com/blender/blender/blob/v4.1.0/extern/cuew/src/cuew.c#L710), [hipew.c#L456](https://github.com/blender/blender/blob/v4.1.0/extern/hipew/src/hipew.c#L456); formats [util.h#L36](https://github.com/blender/blender/blob/v4.1.0/intern/cycles/device/cuda/util.h#L36), [queue.cpp#L214](https://github.com/blender/blender/blob/v4.1.0/intern/cycles/device/cuda/queue.cpp#L214) | `Error: run out of memory!` [guarded_allocator.h#L159](https://github.com/blender/blender/blob/v4.1.0/intern/cycles/util/guarded_allocator.h#L159) | [device_impl.cpp#L75](https://github.com/blender/blender/blob/v4.1.0/intern/cycles/device/optix/device_impl.cpp#L75), only with `--debug-cycles`/`--verbose` | bare line on stderr: [device.h#L171](https://github.com/blender/blender/blob/v4.1.0/intern/cycles/device/device.h#L171) |
| 4.2 (`v4.2.0`) | [device.cpp#L697](https://github.com/blender/blender/blob/v4.2.0/intern/cycles/device/device.cpp#L697), [metal#L743](https://github.com/blender/blender/blob/v4.2.0/intern/cycles/device/metal/device_impl.mm#L743) | [device.cpp#L701](https://github.com/blender/blender/blob/v4.2.0/intern/cycles/device/device.cpp#L701) | [cuew.c#L710](https://github.com/blender/blender/blob/v4.2.0/extern/cuew/src/cuew.c#L710), [hipew.c#L456](https://github.com/blender/blender/blob/v4.2.0/extern/hipew/src/hipew.c#L456); formats [util.h#L36](https://github.com/blender/blender/blob/v4.2.0/intern/cycles/device/cuda/util.h#L36), [queue.cpp#L214](https://github.com/blender/blender/blob/v4.2.0/intern/cycles/device/cuda/queue.cpp#L214) | `Error: run out of memory!` [guarded_allocator.h#L159](https://github.com/blender/blender/blob/v4.2.0/intern/cycles/util/guarded_allocator.h#L159) | [device_impl.cpp#L75](https://github.com/blender/blender/blob/v4.2.0/intern/cycles/device/optix/device_impl.cpp#L75), only with `--debug-cycles`/`--verbose` | bare line on stderr: [device.h#L176](https://github.com/blender/blender/blob/v4.2.0/intern/cycles/device/device.h#L176) |
| 4.3 (`v4.3.0`) | [device.cpp#L695](https://github.com/blender/blender/blob/v4.3.0/intern/cycles/device/device.cpp#L695), [metal#L698](https://github.com/blender/blender/blob/v4.3.0/intern/cycles/device/metal/device_impl.mm#L698) | [device.cpp#L699](https://github.com/blender/blender/blob/v4.3.0/intern/cycles/device/device.cpp#L699) | [cuew.c#L710](https://github.com/blender/blender/blob/v4.3.0/extern/cuew/src/cuew.c#L710), [hipew.c#L455](https://github.com/blender/blender/blob/v4.3.0/extern/hipew/src/hipew.c#L455); formats [util.h#L36](https://github.com/blender/blender/blob/v4.3.0/intern/cycles/device/cuda/util.h#L36), [queue.cpp#L214](https://github.com/blender/blender/blob/v4.3.0/intern/cycles/device/cuda/queue.cpp#L214) | `Error: run out of memory!` [guarded_allocator.h#L159](https://github.com/blender/blender/blob/v4.3.0/intern/cycles/util/guarded_allocator.h#L159) | [device_impl.cpp#L75](https://github.com/blender/blender/blob/v4.3.0/intern/cycles/device/optix/device_impl.cpp#L75), only with `--debug-cycles`/`--verbose` | bare line on stderr: [device.h#L174](https://github.com/blender/blender/blob/v4.3.0/intern/cycles/device/device.h#L174) |
| 4.4 (`v4.4.0`) | [device.cpp#L706](https://github.com/blender/blender/blob/v4.4.0/intern/cycles/device/device.cpp#L706), [metal#L692](https://github.com/blender/blender/blob/v4.4.0/intern/cycles/device/metal/device_impl.mm#L692) | [device.cpp#L710](https://github.com/blender/blender/blob/v4.4.0/intern/cycles/device/device.cpp#L710) | [cuew.c#L710](https://github.com/blender/blender/blob/v4.4.0/extern/cuew/src/cuew.c#L710), [hipew.c#L447](https://github.com/blender/blender/blob/v4.4.0/extern/hipew/src/hipew.c#L447); formats [util.h#L36](https://github.com/blender/blender/blob/v4.4.0/intern/cycles/device/cuda/util.h#L36), [queue.cpp#L222](https://github.com/blender/blender/blob/v4.4.0/intern/cycles/device/cuda/queue.cpp#L222) | `Error: run out of memory!` [guarded_allocator.h#L154](https://github.com/blender/blender/blob/v4.4.0/intern/cycles/util/guarded_allocator.h#L154) | [device_impl.cpp#L73](https://github.com/blender/blender/blob/v4.4.0/intern/cycles/device/optix/device_impl.cpp#L73), only with `--debug-cycles`/`--verbose` | bare line on stderr: [device.h#L178](https://github.com/blender/blender/blob/v4.4.0/intern/cycles/device/device.h#L178) |
| 4.5 (`v4.5.0`) | [device.cpp#L706](https://github.com/blender/blender/blob/v4.5.0/intern/cycles/device/device.cpp#L706), [metal#L722](https://github.com/blender/blender/blob/v4.5.0/intern/cycles/device/metal/device_impl.mm#L722) | [device.cpp#L710](https://github.com/blender/blender/blob/v4.5.0/intern/cycles/device/device.cpp#L710) | [cuew.c#L720](https://github.com/blender/blender/blob/v4.5.0/extern/cuew/src/cuew.c#L720), [hipew.c#L447](https://github.com/blender/blender/blob/v4.5.0/extern/hipew/src/hipew.c#L447); formats [util.h#L36](https://github.com/blender/blender/blob/v4.5.0/intern/cycles/device/cuda/util.h#L36), [queue.cpp#L222](https://github.com/blender/blender/blob/v4.5.0/intern/cycles/device/cuda/queue.cpp#L222) | `Error: run out of memory!` [guarded_allocator.h#L155](https://github.com/blender/blender/blob/v4.5.0/intern/cycles/util/guarded_allocator.h#L155) | [device_impl.cpp#L74](https://github.com/blender/blender/blob/v4.5.0/intern/cycles/device/optix/device_impl.cpp#L74), only with `--debug-cycles`/`--verbose` | bare line on stderr: [device.h#L167](https://github.com/blender/blender/blob/v4.5.0/intern/cycles/device/device.h#L167) |
| 5.0 (`v5.0.0`) | [device.cpp#L721](https://github.com/blender/blender/blob/v5.0.0/intern/cycles/device/device.cpp#L721), [metal#L603](https://github.com/blender/blender/blob/v5.0.0/intern/cycles/device/metal/device_impl.mm#L603) | [device.cpp#L725](https://github.com/blender/blender/blob/v5.0.0/intern/cycles/device/device.cpp#L725) | [cuew.c#L720](https://github.com/blender/blender/blob/v5.0.0/extern/cuew/src/cuew.c#L720), [hipew.c#L436](https://github.com/blender/blender/blob/v5.0.0/extern/hipew/src/hipew.c#L436); formats [util.h#L36](https://github.com/blender/blender/blob/v5.0.0/intern/cycles/device/cuda/util.h#L36), [queue.cpp#L222](https://github.com/blender/blender/blob/v5.0.0/intern/cycles/device/cuda/queue.cpp#L222) | `Out of memory` [guarded_allocator.h#L155](https://github.com/blender/blender/blob/v5.0.0/intern/cycles/util/guarded_allocator.h#L155) | [device_impl.cpp#L73](https://github.com/blender/blender/blob/v5.0.0/intern/cycles/device/optix/device_impl.cpp#L73), always | `cycles \| ERROR` on stdout: [device.cpp#L57](https://github.com/blender/blender/blob/v5.0.0/intern/cycles/device/device.cpp#L57), [logging.cpp#L25](https://github.com/blender/blender/blob/v5.0.0/intern/cycles/blender/logging.cpp#L25) |
| 5.1 (`v5.1.0`) | [device.cpp#L752](https://github.com/blender/blender/blob/v5.1.0/intern/cycles/device/device.cpp#L752), [metal#L601](https://github.com/blender/blender/blob/v5.1.0/intern/cycles/device/metal/device_impl.mm#L601) | [device.cpp#L756](https://github.com/blender/blender/blob/v5.1.0/intern/cycles/device/device.cpp#L756) | [cuew.c#L720](https://github.com/blender/blender/blob/v5.1.0/extern/cuew/src/cuew.c#L720), [hipew.c#L436](https://github.com/blender/blender/blob/v5.1.0/extern/hipew/src/hipew.c#L436); formats [util.h#L36](https://github.com/blender/blender/blob/v5.1.0/intern/cycles/device/cuda/util.h#L36), [queue.cpp#L222](https://github.com/blender/blender/blob/v5.1.0/intern/cycles/device/cuda/queue.cpp#L222) | `Out of memory` [guarded_allocator.h#L155](https://github.com/blender/blender/blob/v5.1.0/intern/cycles/util/guarded_allocator.h#L155) | [device_impl.cpp#L74](https://github.com/blender/blender/blob/v5.1.0/intern/cycles/device/optix/device_impl.cpp#L74), always | `cycles \| ERROR` on stdout: [device.cpp#L88](https://github.com/blender/blender/blob/v5.1.0/intern/cycles/device/device.cpp#L88), [logging.cpp#L25](https://github.com/blender/blender/blob/v5.1.0/intern/cycles/blender/logging.cpp#L25) |
| 5.2 (`v5.2.0`) | [device.cpp#L785](https://github.com/blender/blender/blob/v5.2.0/intern/cycles/device/device.cpp#L785), [metal#L702](https://github.com/blender/blender/blob/v5.2.0/intern/cycles/device/metal/device_impl.mm#L702) | [device.cpp#L789](https://github.com/blender/blender/blob/v5.2.0/intern/cycles/device/device.cpp#L789) | [cuew.c#L722](https://github.com/blender/blender/blob/v5.2.0/extern/cuew/src/cuew.c#L722), [hipew.c#L436](https://github.com/blender/blender/blob/v5.2.0/extern/hipew/src/hipew.c#L436); formats [util.h#L36](https://github.com/blender/blender/blob/v5.2.0/intern/cycles/device/cuda/util.h#L36), [queue.cpp#L260](https://github.com/blender/blender/blob/v5.2.0/intern/cycles/device/cuda/queue.cpp#L260) | `Out of memory` [guarded_allocator.h#L155](https://github.com/blender/blender/blob/v5.2.0/intern/cycles/util/guarded_allocator.h#L155) | [device_impl.cpp#L74](https://github.com/blender/blender/blob/v5.2.0/intern/cycles/device/optix/device_impl.cpp#L74), always | `cycles \| ERROR` on stdout: [device.cpp#L84](https://github.com/blender/blender/blob/v5.2.0/intern/cycles/device/device.cpp#L84), [logging.cpp#L27](https://github.com/blender/blender/blob/v5.2.0/intern/cycles/blender/logging.cpp#L27) |
| 5.3 (`v5.3.0`) | [device.cpp#L854](https://github.com/blender/blender/blob/v5.3.0/intern/cycles/device/device.cpp#L854), [metal#L684](https://github.com/blender/blender/blob/v5.3.0/intern/cycles/device/metal/device_impl.mm#L684) | [device.cpp#L858](https://github.com/blender/blender/blob/v5.3.0/intern/cycles/device/device.cpp#L858) | [cuew.c#L722](https://github.com/blender/blender/blob/v5.3.0/extern/cuew/src/cuew.c#L722), [hipew.c#L436](https://github.com/blender/blender/blob/v5.3.0/extern/hipew/src/hipew.c#L436); formats [util.h#L36](https://github.com/blender/blender/blob/v5.3.0/intern/cycles/device/cuda/util.h#L36), [queue.cpp#L280](https://github.com/blender/blender/blob/v5.3.0/intern/cycles/device/cuda/queue.cpp#L280) | `Out of memory` [guarded_allocator.h#L159](https://github.com/blender/blender/blob/v5.3.0/intern/cycles/util/guarded_allocator.h#L159) | [device_impl.cpp#L75](https://github.com/blender/blender/blob/v5.3.0/intern/cycles/device/optix/device_impl.cpp#L75), always | `cycles \| ERROR` on stdout: [device.cpp#L84](https://github.com/blender/blender/blob/v5.3.0/intern/cycles/device/device.cpp#L84), [logging.cpp#L27](https://github.com/blender/blender/blob/v5.3.0/intern/cycles/blender/logging.cpp#L27) |

Line moves within a series: Metal L743 → [L748](https://github.com/blender/blender/blob/v4.2.23/intern/cycles/device/metal/device_impl.mm#L748)
from v4.2.1; `device.h` L176 → [L179](https://github.com/blender/blender/blob/v4.2.23/intern/cycles/device/device.h#L179)
from v4.2.8; hipew L456 → [L473](https://github.com/blender/blender/blob/v4.2.23/extern/hipew/src/hipew.c#L473)
from v4.2.9; hipew L447 → [L450](https://github.com/blender/blender/blob/v4.5.16/extern/hipew/src/hipew.c#L450)
from v4.5.3. Metal has six call sites in 4.x and five in 5.x; the table links the first.

**Not matched, on purpose.** Other GPU faults: `Illegal address …`, CUDA error 719,
`OPTIX_ERROR_CUDA_ERROR in optixLaunch(…)`. The "Refer to the Cycles GPU rendering documentation"
hint, which follows any device's first error. OIDN denoiser errors (`OIDN error: out of memory`): the
text comes from OIDN, and Cycles first retries with less memory. Embree's `out of memory error`,
which is a CPU BVH warning. oneAPI and HIP-RT allocation failures, whose text differs. A generic
lowercase `out of memory`, which would match third-party messages like OIDN's.

## How a failure reaches the task

1. A failing callback stores a `RuntimeError` in `_exc_info`. `_handle_out_of_memory` keeps an
   earlier error; `_handle_error` replaces it.
2. `_has_exception` raises `_exc_info` unless cleanup is running.
3. `on_start` checks it every 0.1 s while init actions are queued. `on_run` checks it every 0.1 s
   until the frame completes. Raising from `on_run` fails the task with the exception's message,
   even though Blender may still be running.
4. A failed task ends the session. The step environment's exit (`blender-openjd daemon stop`) runs
   `on_cleanup`. That asks Blender to close, waits 30 s, then terminates it: SIGTERM, then SIGKILL
   after another 60 s.
5. After `_exc_info` is set, the next completion or progress line raises inside its reader thread
   (`_check_for_exception`), and that thread stops reading. The task is already failing, and
   cleanup still terminates Blender.

## Process exit

`--python-exit-code 1` makes an exception in the client exit Blender with code 1. When the wait in
`on_run` ends because Blender stopped running:

| State | Result |
|-------|--------|
| The frame had not completed | `RuntimeError("Blender exited early and did not render successfully, please check render logs. Exit code <n>")`, recorded as a telemetry error |
| The frame completed and the exit code is not 0 | `RuntimeError("Blender reported render completion but exited with a nonzero code. Exit code <n>")`, recorded as a telemetry error |
| The frame completed and the exit code is 0 | The task succeeds |

## Output format by Blender release

| | Blender 4.0–4.5 | Blender 5.0–5.3 |
|---|---|---|
| Cycles device errors (`Device::set_error`) | The bare message on stderr ([device.h#L171](https://github.com/blender/blender/blob/v4.0.0/intern/cycles/device/device.h#L171)) | `LOG_ERROR` ([device.cpp#L57](https://github.com/blender/blender/blob/v5.0.0/intern/cycles/device/device.cpp#L57)) through CLOG log type `cycles` ([logging.cpp#L10](https://github.com/blender/blender/blob/v5.0.0/intern/cycles/blender/logging.cpp#L10), set up at startup by [creator.cc#L520](https://github.com/blender/blender/blob/v5.0.0/source/creator/creator.cc#L520)), on stdout |
| Cycles log lines | glog on stderr ([log.cpp#L36](https://github.com/blender/blender/blob/v4.0.0/intern/cycles/util/log.cpp#L36)): `E0101 00:12:34.567890 12345 device_impl.cpp:74] <message>` ([logging.cc#L1281](https://github.com/blender/blender/blob/v4.0.0/extern/glog/src/logging.cc#L1281)–[#L1293](https://github.com/blender/blender/blob/v4.0.0/extern/glog/src/logging.cc#L1293)) | CLOG, as below |
| GPU documentation hint after a device's first error | stderr ([cuda/device_impl.cpp#L49](https://github.com/blender/blender/blob/v4.0.0/intern/cycles/device/cuda/device_impl.cpp#L49)) | `LOG_ERROR` ([#L52](https://github.com/blender/blender/blob/v5.0.0/intern/cycles/device/cuda/device_impl.cpp#L52)) |
| Reports | `Error: <message>` on stdout ([report.cc#L92](https://github.com/blender/blender/blob/v4.0.0/source/blender/blenkernel/intern/report.cc#L92)) | CLOG log type `reports` ([report.cc#L31](https://github.com/blender/blender/blob/v5.0.0/source/blender/blenkernel/intern/report.cc#L31)) |

A Blender 5 CLOG line is `<time>  <type> | <SEVERITY> <message>`, for example
`01:37.974  cycles           | ERROR Out of memory`:

- `<time>` is the time since Blender started, `MM:SS.mmm`, or `HH:MM:SS.mmm` after an hour,
  followed by two spaces ([clog.cc#L503](https://github.com/blender/blender/blob/v5.0.0/intern/clog/clog.cc#L503);
  enabled at [creator.cc#L404](https://github.com/blender/blender/blob/v5.0.0/source/creator/creator.cc#L404)).
- `<type>` is padded to 16 characters and followed by one space
  ([clog.cc#L545](https://github.com/blender/blender/blob/v5.0.0/intern/clog/clog.cc#L545)),
  then `| ` ([#L600](https://github.com/blender/blender/blob/v5.0.0/intern/clog/clog.cc#L600)).
- INFO and more verbose levels print no severity word
  ([#L523](https://github.com/blender/blender/blob/v5.0.0/intern/clog/clog.cc#L523)).
- The continuation lines of a multi-line message are indented to the `|` and carry no severity
  ([#L602](https://github.com/blender/blender/blob/v5.0.0/intern/clog/clog.cc#L602),
  [#L613](https://github.com/blender/blender/blob/v5.0.0/intern/clog/clog.cc#L613)), so they never
  match a `| ERROR ` anchor.
- Output goes to stdout ([#L827](https://github.com/blender/blender/blob/v5.0.0/intern/clog/clog.cc#L827)).
  It is coloured only when stdout is a terminal
  ([#L718](https://github.com/blender/blender/blob/v5.0.0/intern/clog/clog.cc#L718)), and the
  adaptor reads it through a pipe, so there is no colour.

## Example: Blender 5.0 GPU out of memory

`test/unit/deadline_adaptor_for_blender/data/observed-blender-5.0-gpu-oom-output.txt` holds the
Blender 5.0 lines from two observed failures, with customer data removed. In both cases Blender
stopped rendering and never exited.

| Case | The task fails at |
|------|-------------------|
| A, CUDA | `01:37.974  cycles           \| ERROR Out of memory` |
| B, OptiX | `02:03.969  cycles           \| ERROR cblCudaReconfigureLocalMemory failed with out of memory` |

No other line in the file matches any pattern. That covers the warnings and the missing-image error
printed before the failure. It also covers the lines printed after it: `Illegal address`, the
documentation hint and its continuation lines, `Failed to query command list event`,
`Error launching work to RTX` and `OPTIX_ERROR_CUDA_ERROR`. The unit tests replay the file through
the adaptor's output handler.

## Known gaps

| Gap | Effect | See |
|-----|--------|-----|
| Blender 5 prints no render status line | No progress updates on Blender 5; a frame goes from 0 to 100 | [Pattern 2](#2-render-progress) |
| EEVEE Next in 4.2.0 prints no per-sample status | No EEVEE progress on 4.2.0 | [Pattern 2](#2-render-progress) |
| Blender 5 writes `ERROR` and `WARNING` in capitals | Strict mode misses Blender 5's own errors and warnings | [Pattern 3](#3-strict-error-checking) |
| Blender 4.x relays OptiX messages only with `--debug-cycles` or `--verbose` ([device_impl.cpp#L75](https://github.com/blender/blender/blob/v4.0.0/intern/cycles/device/optix/device_impl.cpp#L75)) | The OptiX out-of-memory message is not seen on 4.x | [Pattern 5](#5-out-of-memory) |
| A reader thread raises once `_exc_info` is set | That stream stops being read; cleanup still terminates Blender | [How a failure reaches the task](#how-a-failure-reaches-the-task) |

## Changing this behavior

When you add, remove or change a pattern or a callback:

1. Update this document in the same commit, with the pattern, its effect and its text source. Pin
   Blender links to release tags (`https://github.com/blender/blender/blob/<tag>/<path>#L<line>`)
   for each 4.x and 5.x release whose code differs.
2. Add a unit test that feeds the line, in each Blender release's format, through
   `RegexHandler(adaptor._get_regex_callbacks())`, and assert the full error message.
3. Remove customer data (names, paths, IDs) from any real Blender output you commit as a fixture.

## References

- Blender source: https://github.com/blender/blender. Every tag from `v4.0.0` to `v5.3.0` was
  checked for the out-of-memory messages; the other patterns were checked at each series' `.0`
  tag and the tags named above.
- openjd-adaptor-runtime-for-python 0.9.6:
  https://github.com/OpenJobDescription/openjd-adaptor-runtime-for-python/tree/0.9.6
