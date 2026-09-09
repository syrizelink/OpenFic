## Contributing to OpenFic

### Bugs

If you find a bug and plan to submit a patch, make sure that:
- You can reproduce the bug on the latest version.
- The bug is not already addressed by changes committed to the `main` branch but not yet released.
- No open or draft PR already covers the bug.

After you finish the patch:
- Open a PR.
- Make sure the PR description follows [the template](./.github/PULL_REQUEST_TEMPLATE.md) and clearly explains the cause of the problem and the solution.
- Assign reviewers and wait for review.

## New features

If you plan to add a new feature or improve an existing one, keep the following in mind:
- Changes to core Harness modules, such as `backend/app/agent_runtime`, are usually rejected. These changes affect a wide area of the project and can introduce subtle, unexpected problems.
- For frontend changes, especially UI changes, make sure they meet all of the following requirements. PRs in this area often take longer to review and may require more revisions:
  - They follow the project's overall style.
  - They include complete mobile layout support.
  - They consider UX, including the mobile experience.
  - They do not affect other layouts.
- A PR for a new feature may be closed rather than sent back for changes if it does not fit the project's goals. We respect everyone's ideas, but we select features carefully. If you are unsure whether a feature is a good fit, use a Discussion to get feedback. You can also fork the repository and make your own changes.

## Notes

If your contribution only reformats code, addresses issues that have no effect on actual behavior or UX, or makes a superficial functional fix, it is unlikely to improve the system's stability or functionality in a meaningful way. Such PRs will be closed.

OpenFic relies on community contributions. Thanks to everyone who opens issues and PRs ♥️♥️♥️.
