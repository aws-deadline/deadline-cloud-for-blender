# Using the Deadline Cloud submitter installer

You can install the Deadline Cloud for Blender submitter using the Deadline Cloud submitter installer.

**To install the submitter**

1. Download the [Deadline Cloud submitter installer](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/submitter.html).
1. Run the installer and follow the prompts.
1. Launch Blender.

The Deadline Cloud submitter add-on should be automatically enabled.
> The submitter installer is available for Windows, MacOS, and Linux. See the [developer README](https://github.com/aws-deadline/deadline-cloud-for-blender/blob/mainline/README.md) for manual installation instructions.

**To verify the submitter is installed correctly**

1. Open Blender.
1. On the **Edit** menu, choose **Preferences…**.
1. Choose **Add-ons** on the left side bar.
1. Search for `Deadline Cloud`.
1. You should see the **AWS Deadline Cloud for Blender Submitter** add-on listed and enabled.

If the add-on is not available from the **Render** menu, you will need to manually enable it.

**To manually enable the submitter add-on**

1. On the **Edit** menu, choose **Preferences…**.
1. Choose **File Paths** on the left side bar.
1. Find the **Script Directories** section and choose **+**.
1. For **Name**, enter `python`.
1. For **Path**, enter the path to the `python` directory in your Blender submitter installation.
1. Restart Blender for changes to take effect.
