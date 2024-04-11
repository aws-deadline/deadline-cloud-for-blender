# Job bundle output tests

A collection of test scenes and expected output job bundles can be found in [job_bundle_output_tests](https://github.com/aws-deadline/deadline-cloud-for-blender/job_bundle_output_tests)

## Running the job bundle output tests
The job bundle tests are run manually by doing the following:
1. Set the environment variable `DEADLINE_ENABLE_DEVELOPER_OPTIONS=True`
1. Launch Blender
1. Press the `Render->Run Job Bundle Output Tests` button in Blender's UI
1. A popup will open asking you to select the directory containing the job bundle tests.
 Select the [job_bundle_output_tests](https://github.com/aws-deadline/deadline-cloud-for-blender/job_bundle_output_tests) folder from this repository as the directory holding 
the tests
1. The tests will now run and a message will be displayed at the end of how many
have succeeded and failed
1. An output file `blender-test-job-bundle-results.txt` will be created in the
`job_bundle_output_tests` directory and the contents of that file should be copied
into your pull request

## Creating new job bundle output tests

Each of the job bundle tests consists of the following structure:

```
└───TEST_NAME
    ├───expected_job_bundle
    │       asset_references.yaml
    │       parameter_values.yaml
    │       template.yaml
    │
    └───scene
            TEST_NAME.blend
            Other assorted scene files
```

Note that the scene name **needs** to match the name of the test from the top level folder it's contained in.

To create a new test:
1. Create a new Blender scene file that when exported as a job bundle by the submitter uses the functionality you wish to test
1. The first run of a new test should "Fail", but generate the `expected_job_bundle` folder and contents for you
1. Inspect the `asset_references`, `parameter_values` and `template` files to verify that they look correct based on the scene provided and the expected behviour being tested. Subsequent runs should now compare against the `expected_job_bundle` and succeed.
1. Put up a PR to include your new test