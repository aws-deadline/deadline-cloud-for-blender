# Blender Adaptor Specifications

Design specifications for `deadline.blender_adaptor`, the `blender-openjd` adaptor that runs
Blender on AWS Deadline Cloud workers through the Open Job Description adaptor runtime.

## Document Index

| Document | Description |
|----------|-------------|
| [log-handling.md](log-handling.md) | How the adaptor reads Blender's output, every pattern it matches, what each match does, and which code prints the matched text in each Blender release from 4.0 to 5.3 |

## Components

| Path | Runs in | Role |
|------|---------|------|
| `src/deadline/blender_adaptor/BlenderAdaptor/` | The adaptor process | Starts Blender, queues actions, reads Blender's output, and completes or fails each task |
| `src/deadline/blender_adaptor/BlenderClient/` | Blender's Python | Connects back to the adaptor, runs its actions (open the scene, render a frame) and prints the marker lines the adaptor matches |

## References

- [openjd-adaptor-runtime-for-python](https://github.com/OpenJobDescription/openjd-adaptor-runtime-for-python):
  the adaptor lifecycle (`on_start`, `on_run`, `on_cleanup`), `LoggingSubprocess` and `RegexHandler`.
- [Blender source](https://github.com/blender/blender), release tags `v4.0.0` to `v5.3.0`.
