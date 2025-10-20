# Using the Deadline Cloud submitter installer

You can install the Deadline Cloud for Blender submitter using the Deadline Cloud submitter installer.

**To install the submitter**

1. Download the [Deadline Cloud submitter installer](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/submitter.html).
1. Run the installer.
    - When prompted, select each version of Blender you want to use the submitter with.
1. Launch Blender.
1. Verify the installation by checking the **Render** menu for a **Submit to AWS Deadline Cloud** option.

If the add-on is not available from the **Render** menu, you will need to manually enable it.

**To manually enable the submitter add-on**

1. On the **Edit** menu, choose **Preferences…**.
1. Choose **File Paths** on the left side bar.
1. Find the **Script Directories** section and choose **+**.
1. For **Name**, enter `python`.
1. For **Path**, enter the path to the `python` directory in your Blender submitter installation.
1. Restart Blender for changes to take effect.
