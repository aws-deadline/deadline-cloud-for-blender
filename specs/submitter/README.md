# Blender Submitter Specifications

Design specifications for `deadline_cloud_blender_submitter`, the Blender add-on that creates AWS
Deadline Cloud jobs from a scene.

## Document Index

| Document | Description |
|----------|-------------|
| [timeouts.md](timeouts.md) | Every time limit on a Blender job's actions, the configurable task run timeout, and what happens when each limit is reached |

## Components

| Path | Role |
|------|------|
| `src/deadline/blender_submitter/addons/deadline_cloud_blender_submitter/default_blender_template.yaml` | The job template the submitter starts from |
| `src/deadline/blender_submitter/addons/deadline_cloud_blender_submitter/template_filling.py` | The settings dataclasses, their sticky settings, and the builders that fill the template and its parameter values |
| `src/deadline/blender_submitter/addons/deadline_cloud_blender_submitter/scene_settings_widget.py` | The submitter's "Job-specific settings" tab |
| `src/deadline/blender_submitter/addons/deadline_cloud_blender_submitter/open_deadline_cloud_dialog.py` | Opens the dialog, converts the UI settings to `BlenderSubmitterSettings`, and writes the job bundle |
| `src/deadline/blender_submitter/addons/deadline_cloud_blender_submitter/submitter.py` | `BlenderSubmitter`, which builds the template and parameter values for the dialog and for API submissions |

The adaptor that runs the job on workers is specified in [`../adaptor/README.md`](../adaptor/README.md).

## References

- [Open Job Description 2023-09 template schemas](https://github.com/OpenJobDescription/openjd-specifications/wiki/2023-09-Template-Schemas):
  `<Action>` timeouts and `<CancelationMethod>`.
- [deadline-cloud](https://github.com/aws-deadline/deadline-cloud) 0.60.12, the lowest version
  `pyproject.toml` accepts: the submitter dialog and the shared timeout widget.
