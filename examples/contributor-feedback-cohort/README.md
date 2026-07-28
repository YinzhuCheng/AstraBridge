# Pre-Preview Contributor Feedback Cohort

This directory defines a bounded rehearsal cohort, not an open code intake.
It starts with the existing provider-free candidate skill example twice in
independent empty roots, then records the same safe review and response
expectation that the issue templates carry.

The cohort is useful before licensing is complete because it proves that a
developer can inspect one finite candidate, run local validation, encounter an
authority-widening block, and prepare a redacted proposal without credentials,
provider calls, or hidden maintainer state.

For retained local evidence, run the cohort through
`python scripts/run_contributor_feedback_cohort_rehearsal.py --output-root PRIVATE\contributor-cohort\reports\rehearsal`.
The output root must be empty; the `reports/` bucket keeps the retained packet
compatible with the repository artifact-governance scan. The runner does not
open an issue, send a message, activate public intake, create a private
reporting route, or accept merge-ready code.
