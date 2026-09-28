# Data sources and refresh policy

`Model.xlsx` is the canonical release snapshot. The maintained source sheet may change between releases, but a source edit becomes public only after the notebook has run end to end and every release gate passes.

## Source roles

The workbook combines national indicators, historical election results, generic-ballot and race polling, ratings, candidate/incumbency information, district and state fundamentals, and source-control metadata. Each sheet has a defined modeling or audit role; retired aggregate result buckets are not allowed to re-enter production predictors.

Senate polling sources are included through the Senate parser/source controls when active in the workbook. A retired third-party API is not equivalent to retiring the Senate polling parser itself.

## Refresh rules

1. Update values and source metadata in the maintained sheet.
2. Export the intended snapshot as `Model.xlsx`.
3. Restart the notebook kernel and run all cells in order.
4. Confirm the final and post-HTML release gates pass.
5. Publish the notebook, consolidated report, HTML and workbook together.

The repository does not contain credentials. Do not commit private API keys, service-account files, browser sessions or unpublished personal data.
