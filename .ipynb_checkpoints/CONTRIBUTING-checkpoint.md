# Contributing

Thank you for helping improve the Midterms 2026 Forecast Model. Contributions are welcome when they make the project more accurate, reproducible, transparent, or understandable.

## Before opening an issue

1. Search existing issues and the latest release notes.
2. Identify whether the observation concerns data, methodology, reproducibility, presentation, or documentation.
3. Reproduce the behavior with the current repository or the tagged release you are reviewing.
4. Record the operating system, Python version, notebook filename, workbook snapshot, and exact command when relevant.

Use the provided issue templates. A methodological disagreement is not a software bug; a different live-data result is not necessarily a reproducibility failure unless the same frozen input produces inconsistent output.

## Contribution categories

- **Data correction:** a sourced correction to a workbook value, definition, date, race, or district.
- **Methodology review:** an observation about temporal validation, selection, regularization, leakage, constraints, uncertainty, or interpretation.
- **Reproducibility report:** an environment, dependency, notebook, asset, or map-rebuild failure.
- **Dashboard improvement:** an accessibility, interaction, labeling, visual, or responsive-layout change.
- **Feature proposal:** a scoped extension with a clear analytical purpose and testable acceptance criteria.

## Pull-request workflow

1. Fork the repository and create a focused branch.
2. Keep each pull request limited to one coherent change.
3. Preserve worksheet names and expected column positions unless the pull request explicitly includes a coordinated schema migration.
4. Separate statistical-logic changes from presentation-only changes whenever possible.
5. Do not use outer-fold predictions as synthetic rows in the production fit.
6. Do not introduce downstream Senate or House information into frozen national estimates.
7. Add or update validation evidence for every methodological or data change.
8. Run:

   ```bash
   python scripts/validate_repository.py
   ```

9. Complete the pull-request checklist and explain the effect on results, uncertainty, and reproducibility.

## Evidence expectations

A methodology pull request should state:

- the problem being addressed;
- the proposed statistical change;
- what information is available at each validation stage;
- whether the change alters model selection, tuning, production fitting, constraints, or simulations;
- comparative out-of-sample evidence;
- stability and sensitivity effects; and
- any limitation introduced by the change.

A data correction should link to a primary or authoritative source whenever one exists and identify every downstream artifact that must be regenerated.

## Style

- Python should be readable, deterministic, and explicit about random seeds.
- Paths should be relative to the repository root.
- Generated values should not be hard-coded into the dashboard.
- Public-facing dashboard copy and repository documentation should remain in English.
- New dependencies require a clear justification and must be pinned in `requirements.txt`.

## Review and recognition

Opening a contribution does not guarantee acceptance. Substantive accepted contributions will be recognized appropriately in release notes and project materials. All contributors must follow the repository Code of Conduct.
