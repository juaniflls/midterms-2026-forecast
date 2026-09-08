# Data Sources & Snapshot Policy

## Frozen release
`Model.xlsx` is the exact frozen workbook used by NUCLEUS 42 v27.1.

## Live canonical Model sheet
https://docs.google.com/spreadsheets/d/1NC80MaJh8vyxrbQsi__HSR2StaSo8mgAJ3iSdilqEj0/edit?usp=sharing

The live sheet is maintained separately and is not the frozen release artifact.

A future release should:
1. export the maintained sheet as `Model.xlsx`;
2. refresh approved current-cycle sources;
3. run the notebook from a clean kernel;
4. validate report + HTML + Dash;
5. freeze the resulting artifacts as a new version.

## Data families
Historical election results, national political/economic indicators, House district fundamentals/ratings/polling, Senate polling/ratings, current-cycle PVI, candidate/incumbent information, official Census CD120 geography, and generated model audits.

Third-party data remain subject to their own terms.
