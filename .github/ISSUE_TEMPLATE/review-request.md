---
name: AIMCR review / change request
about: Track a new proposal review or a change-request addendum, from intake to sign-off.
title: "[AIMCR] <project ID> (<PI last name>) — <IMS / RITM number>"
labels: review
assignees: ''
---

<!--
One issue per proposal review or per change request.
Branch naming: <project ID>-<PI last name>/main for the proposal,
<project ID>-<PI last name>/<IMS or RITM number> for each change request
(e.g. 65638-elhoseiny/IMS0000192).
-->

## Request

| | |
|---|---|
| **Review type** | New proposal review / Change request (addendum) / Resubmission or correction |
| **Project ID** | 6#### or RITM number |
| **Principal investigator** | |
| **Proposal title** | |
| **Change request ticket** | IMS####### or RITM####### (leave empty for a new proposal review) |
| **Request date / due date** | |
| **Branch** | `<project ID>-<PI last name>/<IMS or RITM number>` |

## Artifacts to review

List each artifact with name, version and source link. For a change request, mark each as **New**, **Modified**, **Carry-forward** or **Dropped**.

**Third-party software**
-

**Source code**
-

**Datasets / user files**
-

**Models**
-

## Source documents

- Proposal / CR form:
- Data location (e.g. on Ibex):
- Review JSON: `submissions/AIMCR-<project ID>-<DD-MM-YYYY>/aimcr_data.json`

## Review progress

- [ ] Artifacts extracted and sorted into categories (delta list confirmed for a change request)
- [ ] Evidence collected (alignment, LC 2.7 terms, owners/affiliations, source, licence)
- [ ] Dependency dry-run and Trivy CVE scan done (software)
- [ ] Sample inspection done, skipped or waived (datasets / models)
- [ ] FLOPs estimate (6·N·D) checked against 10^27 (models)
- [ ] Every check scored with the rubric and noted with the template wording
- [ ] Observations and recommendation written
- [ ] Validator run with no errors (`validate_aimcr.py`)
- [ ] JSON saved in `submissions/` and pushed on the review branch
- [ ] Pull request opened and linked below
- [ ] Signed off by Mohsin

## Open questions for the PI

Sent through Mohsin, never to the PI directly. Record the date asked and the answer.

- [ ] YYYY-MM-DD: <question>. Answer: pending

## Result

Fill in at the end: section scores, pass/fail, elevated scores and their reasons, monitoring items.

- Pull request: #
