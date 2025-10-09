# Telemetry

This library collects telemetry data by default. Telemetry events contain non-personally identifiable information that helps us understand how users interact with our software. We use this to know which features our customers use and/or what existing pain points are.

You can opt out of telemetry on your machine by editing your Deadline Cloud configuration, or temporarily by setting an environment variable in your terminal.

**To opt out of telemetry (config)**

1. Run the `deadline config` command:
```sh
deadline config set telemetry.opt_out true
```

**To opt out of telemetry (terminal)**

1. Set the environment variable from a terminal:
```sh
DEADLINE_CLOUD_TELEMETRY_OPT_OUT=true
```
1. Launch Blender from the same terminal.


An environment variable value will always be used instead of the configuration setting, if it exists.