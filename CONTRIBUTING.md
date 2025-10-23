# Contributing Guidelines

Thank you for your interest in contributing to our project. Whether it's a bug report, new feature, correction, or additional
documentation, we greatly value feedback and contributions from our community.

Please read through this document before submitting any issues or pull requests to ensure we have all the necessary
information to effectively respond to your bug report or contribution.

## Reporting Bugs/Feature Requests

We welcome you to use the GitHub issue tracker to report bugs or suggest features.

When filing an issue, please check existing open, or recently closed, issues to make sure somebody else hasn't already
reported the issue. Please try to include as much information as you can. Details like these are incredibly useful:

* A reproducible test case or series of steps
* The version of our code being used
* Any modifications you've made relevant to the bug
* Anything unusual about your environment or deployment

## Development

Please see [DEVELOPMENT.md](./DEVELOPMENT.md) for more information.

## Contributing via Pull Requests

Contributions via pull requests are much appreciated. Before sending us a pull request, please ensure that:

1. You are working against the latest source on the *main* branch.
2. You check existing open, and recently merged, pull requests to make sure someone else hasn't addressed the problem already.
3. You open an issue to discuss any significant work - we would hate for your time to be wasted.

To send us a pull request, please:

1. Fork the repository.
2. Modify the source; please focus on the specific change you are contributing. If you also reformat all the code, it will be hard for us to focus on your change.
3. Ensure local tests pass.
4. Commit to your fork using clear commit messages.
5. Send us a pull request, answering any default questions in the pull request interface.
6. Pay attention to any automated CI failures reported in the pull request, and stay involved in the conversation.

GitHub provides additional documentation on [forking a repository](https://help.github.com/articles/fork-a-repo/) and
[creating a pull request](https://help.github.com/articles/creating-a-pull-request/).

### Conventional commits

The commits in this repository are all required to use [conventional commit syntax](https://www.conventionalcommits.org/en/v1.0.0/)
in their title to help us identify the kind of change that is being made, automatically generate the changelog, and 
automatically identify next release version number. Only the first commit that deviates from mainline in your pull request
must adhere to this requirement.

We ask that you use these commit types in your commit titles:

* `feat` - When the pull request adds a new feature or functionality;
* `fix` - When the pull request is implementing a fix to a bug;
* `test` - When the pull request is only implementing an addition or change to tests or the testing infrastructure;
* `docs` - When the pull request is primarily implementing an addition or change to the package's documentation;
* `refactor` - When the pull request is implementing only a refactor of existing code;
* `ci` - When the pull request is implementing a change to the CI infrastructure of the packge;
* `chore` - When the pull request is a generic maintenance task.
* `perf` - When the pull request is a performance improvement.

We also require that the type in your conventional commit title end in an exclaimation point (e.g. `feat!` or `fix!`)
if the pull request should be considered to be a breaking change in some way. Please also include a "BREAKING CHANGE" footer
in the description of your commit in this case ([example](https://www.conventionalcommits.org/en/v1.0.0/#commit-message-with-both--and-breaking-change-footer)).
Examples of breaking changes include:

*   removing a feature of the DCC integration
*   changing established behavior of the integration that users have come to rely on
*   breaking backwards-compatibility between the submitter and and the adaptor

If you need change a commit message, then please see the
[GitHub documentation on the topic](https://docs.github.com/en/pull-requests/committing-changes-to-your-project/creating-and-editing-commits/changing-a-commit-message)
to guide you.

## Finding contributions to work on

Looking at the existing issues is a great way to find something to contribute on. As our projects, by default, use the default GitHub issue labels (enhancement/bug/duplicate/help wanted/invalid/question/wontfix), looking at any 'help wanted' issues is a great place to start.


## Code of Conduct

This project has adopted the [Amazon Open Source Code of Conduct](https://aws.github.io/code-of-conduct).
For more information see the [Code of Conduct FAQ](https://aws.github.io/code-of-conduct-faq) or contact
opensource-codeofconduct@amazon.com with any additional questions or comments.


## Security issue notifications

We take all security reports seriously. When we receive such reports, we will 
investigate and subsequently address any potential vulnerabilities as quickly 
as possible. If you discover a potential security issue in this project, please 
notify AWS/Amazon Security via our [vulnerability reporting page](http://aws.amazon.com/security/vulnerability-reporting/)
or directly via email to [AWS Security](aws-security@amazon.com). Please do not 
create a public GitHub issue in this project.

## Licensing

See the [LICENSE](LICENSE) file for our project's licensing. We will ask you to confirm the licensing of your contribution.
