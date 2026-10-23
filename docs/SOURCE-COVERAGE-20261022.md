# Source coverage and real-data check — October 22, 2026

This is a read-only source review, not a claim that fresh profitable deals were found or that every source has been accepted in production. The machine-readable public check is `PUBLIC-SOURCE-CHECK-20261022.json`.

## Actual ownership

Bob's worker reads canonical saved leads and assembles call briefs, valuation evidence, objectives and feedback. The canonical REI application's `backend/scout` owns discovery adapters. A functioning Bob brief worker therefore does not by itself prove that discovery ran. Canonical producer, shared database, Sophia and dashboard must be tested as one chain.

| Source / adapter | Invocation in canonical REI | Dependency / evidence | Current acceptance |
| --- | --- | --- | --- |
| Propwire-style CSV | `run_scout`, included in `run_scout_cycle` | Actual export in configured scripts/data directory; valid canonical persistence | Code tested with bounded fixtures; no current private export or live persistence accepted in this pass |
| Approved RSS registry | `run_rss_scraper`, included in cycle | Explicit `SCOUT_RSS_FEEDS`; default registry empty | An empty registry is unconfigured coverage, not proof of zero opportunities |
| HomeHarvest listing candidates | `run_expired_scraper`, included in cycle | Installed adapter, provider availability and permitted use | Candidate validation has tests; live access/coverage and data rights remain unverified |
| Craigslist/social FSBO candidates | `run_social_scraper`, included in cycle | Public source access/markup; permitted use; canonical candidate review | Live coverage and recall not accepted; social title/location text is not verified property identity or motivation |
| Court eviction candidates | `run_eviction_scraper`, included in cycle | Actual permitted searchable records and parsable case data | A reachable informational page is not a functioning case-search feed; ownership/property match remains review-only |
| CRMLS listings | `run_crmls_scraper`, included in cycle | Appropriate API account, member configuration, geographic coverage and license | Not claimed live without real credentials, successful fetch and permitted-use evidence |
| County tax-source script | `scripts/seed_tax_delinquent.py`; not in normal scout cycle | Current authoritative notice/status and parcel evidence | One-off legacy scraper traverses auction-page PDFs; historical results must not be interpreted as current verified delinquency |
| Court/probate one-off | `run_weekly_scrape` / seed script; not in normal scout cycle | Approved access, owner identity and parcel match | Must not be described as automatically running in the main discovery cycle |
| Cash-buyer scraper | Separate buyer discovery | Buyer qualification and permitted source access | Buyer contacts are not seller leads or a source of closed-sale ARV truth |
| County parcel service | Parcel identity/characteristics evidence | Exact APN match, current response, source/date | Context only; assessment is not consideration, ARV, title, consent or current delinquency |

Scheduling the six core functions is source-confirmed. These functions do not all return rich operational health, so an apparently completed scout cycle still does not prove every source worked. Production source health/freshness monitoring and integration of additional approved sources remain open. Live validation must report skipped/unconfigured/failed/empty/saved states separately.

## Public records checked now

The official auction page returned a next-auction date of TBD. Its linked March 11–12, 2026 results are historical auction outcomes, not a fresh list of houses currently for sale. The downloaded results contained four explicitly sold rows. Their prices are retained as tax-auction observations with condition unverified and `arv_target_eligible=false`; they are not general-market closed-comparable or completed-renovation ground truth.

The linked default notice identifies defaults as of July 1, 2025 and redemption amounts as of September 2026. Rechecking the previous 15 APNs against extracted text from the currently downloaded notice found 11. Four were not found in this extraction. **Not found is not proof of redemption, sale or absence from all official records.** This requires case-specific tax/title/status review. No current owner, contact permission, seller motivation, ARV or deal profitability was verified, and no new verified-deal count is asserted.

Downloaded source URLs, response status, hashes, page counts and per-APN checks are retained in JSON. No owner names or contact details are retained in that report. Original PDF interpretation was checked visually. Third-party search snippets can reflect a different document version; use the actual retrieved bytes and hashes for reproducibility.

## Repairs tied to this review

The coordinated REI change makes CSV property-write confirmation mandatory, isolates failed records, counts only successful provider-accepted owner alerts, and stores imported contacts without setting `callable` or granting contact authority. Repeated discovery of an existing lead does not repeat initial actions. These tests establish the software behavior with controlled fixtures, not an actual successful production scout run.

## Still required for live lead-quality acceptance

1. Obtain permitted configured source access and current data, then run each adapter with its real runtime configuration.
2. Keep a dated accepted/saved/rejected/duplicate/stale/error record and provenance for every candidate.
3. Verify identity, current availability/redemption/title status, relevant owner authority, contact quality and lawful contact permission.
4. Independently review a blinded sample and measure precision, misses, stale records and source coverage.
5. Produce property-specific comps, conditional ARV and complete offer underwriting only where the evidence supports them; abstain otherwise.
6. Trace accepted records through Bob, Sophia and the live dashboard without contacting sellers merely because a public record was found.

Primary source pages read October 22, 2026:
- https://www.sjgov.org/department/ttc/tax/redemption/public-auction
- https://www.sjgov.org/department/ttc/tax/general-tax/announcements

Exact linked document URLs and retrieval hashes are in the companion JSON. No public-record observation authorizes outreach or an offer.
