# Bugs

All four found by the org edge-case tests and fixed with the test kept (tests written first, seen failing, then fixed). The fix lives in the working tree; the auto-commit hook records the commits.

## B1 [S2] First sign-in race returns 500
- Steps: a new account's browser sends several `GET /v1/orgs` at once (two tabs, or a retry).
- Expected: 200 each, one personal org.
- Actual: the losing request hit the unique `slug` constraint and surfaced as an unhandled error (500).
- Evidence: `test_concurrent_first_org_listing_provisions_one_personal_org`, `UniqueViolationError ... uq_organizations_slug`.
- Fix: `ensure_personal_org` creates inside a savepoint and, on `slug_taken`, reads back the winner's row. Test: same.

## B2 [S3] Blank organization name accepted
- Steps: `POST /v1/orgs {"name": "   ", "slug": "blank"}`.
- Expected: 422. Actual: 201 with an empty name (strip happened after validation).
- Fix: `StringConstraints(strip_whitespace=True, min_length=1, max_length=200)`. Test: `test_org_name_must_not_be_blank_after_trimming`.

## B3 [S3] Invite accepts any string as email
- Steps: `POST /v1/orgs/{id}/invites {"email": "not-an-email"}`.
- Expected: 422. Actual: 201, an invite nobody can accept.
- Fix: pattern on the field. Test: `test_invite_rejects_malformed_email`.

## B4 [S3] Viewers locked out of read-only org endpoints
- Steps: a viewer calls `GET /v1/orgs/{id}/members`, `/products`, `/usage`.
- Expected: 200 (viewer = read access per architecture.md). Actual: 403, because the read guard required `member`.
- Fix: read guard is `viewer`; writes stay `admin`. Tests: `test_viewer_cannot_enable_products_or_manage_members`, `test_accepting_invite_when_already_member_conflicts`.

## Open S1 / S2
None known.

## To check (not reproduced, not claimed as bugs)
- Deleting an account that created an org: `organizations.created_by` has no cascade, so the delete would be blocked. No account-deletion flow exists yet; decide the rule before building it.
- Rows created after the 0009 backfill by the existing routers have `org_id = NULL` (known gap, backend.md).
- Four object-storage tests fail only because the MinIO image cannot be pulled here; unverified, unrelated to this work.
- Console screens and public pages: never rendered in a browser (no Clerk keys).
