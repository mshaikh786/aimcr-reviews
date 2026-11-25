Refs #

## Review

| Field | Value |
|---|---|
| Review type | New proposal review / Change request (addendum) / Resubmission or correction |
| Project ID | |
| PI | |
| Ticket | IMS / RITM number, or n/a |
| Target branch | `main` (new proposal) or `<project ID>_<PI last name>` (CR / correction) |
| Review JSON | `submissions/AIMCR-<project ID>-<DD-MM-YYYY>/aimcr_data.json` |

## What changes

Artifacts added, modified or dropped in this review. For a change request, list the delta only.

## Section results

| Section | Score | Result |
|---|---|---|
| Third-party software | | Pass / Fail |
| Source code | | Pass / Fail |
| Datasets & user files | | Pass / Fail |
| Models | | Pass / Fail |

## Worth a look

Elevated scores (≥ 2) with one-line reasons, D5+M findings, licence issues, PI clarifications.

## Pending actions

Sample inspections during data movement, monitoring items, PI notifications. Write "None" if empty.

## Checklist

- [ ] Branch name follows the convention and the PR targets the right branch
- [ ] `validate_aimcr.py` passes with no errors
- [ ] CR only: new and modified artifacts are in `addenda`; carry-forward entries untouched; `aimcr_date` updated
- [ ] Observations and recommendation written
- [ ] Linked issue progress checklist complete
