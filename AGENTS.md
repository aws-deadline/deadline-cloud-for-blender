# AGENTS.md

> **Before you change how the adaptor handles Blender's output**, read
> [`specs/adaptor/log-handling.md`](specs/adaptor/log-handling.md) and follow it. This covers a
> pattern in `_get_regex_callbacks`, a `_handle_*` callback, and how a failure reaches the task.
> Update the spec in the same commit as the code.

## Project Overview

deadline-cloud-for-blender connects Blender to [AWS Deadline Cloud](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/what-is-deadline-cloud.html).
It has two parts:

- **Submitter** (`src/deadline/blender_submitter/`): a Blender add-on that creates Deadline Cloud
  jobs from a scene.
- **Adaptor** (`src/deadline/blender_adaptor/`): `blender-openjd`, an
  [Open Job Description adaptor](https://github.com/OpenJobDescription/openjd-adaptor-runtime-for-python)
  that runs Blender on workers. `BlenderAdaptor/` runs in the adaptor process. `BlenderClient/`
  runs inside Blender.

See [README.md](README.md) for user documentation, [DEVELOPMENT.md](DEVELOPMENT.md) for developer
setup, and [CONTRIBUTING.md](CONTRIBUTING.md) for pull requests.

## Quick Reference

```bash
hatch build              # Build the wheel
hatch run test           # Unit tests (test/unit)
hatch run lint           # ruff, black --check, mypy src test
hatch run fmt            # Apply black, then run the style checks
hatch run integ:test     # Integration tests; needs BLENDER_EXECUTABLE (see DEVELOPMENT.md)
```

## Specs

`specs/` holds the design specifications. Start at the index for the part you are changing:

- [`specs/adaptor/README.md`](specs/adaptor/README.md) for the adaptor.
- [`specs/submitter/README.md`](specs/submitter/README.md) for the submitter. Read
  [`specs/submitter/timeouts.md`](specs/submitter/timeouts.md) before changing an action's timeout,
  the Timeouts box, or the adaptor's own time limits.

### Spec and code change together

Before committing, confirm that the spec and the code agree. If you changed behavior, update the
spec to describe it. If you changed the spec, make the code match.

For the adaptor's handling of Blender's output ([`specs/adaptor/log-handling.md`](specs/adaptor/log-handling.md)):

- List every pattern the adaptor matches, with its effect and the code that prints the text. Link
  Blender code at release tags (`https://github.com/blender/blender/blob/<tag>/<path>#L<line>`)
  for each 4.x and 5.x release whose code differs.
- Test a new or changed pattern with a unit test that feeds the line, in each Blender release's
  format, through `RegexHandler(adaptor._get_regex_callbacks())`.
- Remove customer data (names, paths, IDs) from real Blender output before committing it as a test
  fixture. `test/unit/deadline_adaptor_for_blender/data/` holds such fixtures.

## Conventions

### Commit messages

Use [conventional commit](https://www.conventionalcommits.org/en/v1.0.0/) titles, with the types
`feat`, `fix`, `test`, `docs`, `refactor`, `ci`, `chore` and `perf`. Add `!` and a
`BREAKING CHANGE` footer for a breaking change. See [CONTRIBUTING.md](CONTRIBUTING.md).

### Tests

When a test checks a failure, assert the full error message (`str(exc_info.value) == ...`), not
only that an error was raised.

### Code style

CI runs the unit tests on Python 3.9 to 3.13 on Linux, macOS and Windows, so code and tests must
work on all of them. The line length is 100, and `hatch run lint` must pass.
