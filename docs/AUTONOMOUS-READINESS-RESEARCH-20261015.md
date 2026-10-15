# San Joaquin operational readiness research

Research checkpoint: October 15, 2026, Pacific. Scope: Bob discovery/valuation, canonical REI Sophia communications and scheduling, and Karpathys source projection. This is a practical release specification, not exhaustive knowledge of every California property or a verified autonomous deployment. No paid data was purchased, seller contacted, production secret retrieved, or live migration run.

## Current decision

Do not enable unrestricted unattended outbound operation or claim local ARV accuracy yet. Source repairs have substantial regression evidence, but external acceptance and some implementation gaps remain. Reading documentation cannot establish a running service, deliver a message, inspect a building, or acquire licensed closed-sale data.

Source checkpoint: REI PR 13 merged as ef7289556abc0d0fdcc6a7badc9a7255b882dac4; 3,621 Python tests and 41% measured branch-aware coverage. Dashboard PR 11 merged as 15a3c8bbc6fc7ae19e414d3077aab54943422e68; 1,151 backend tests, 30 frontend tests, 51 browser states without automated axe findings, and real HTTP/PostgreSQL restart/outage/lost-ack checks. Bob's preceding source head is 44059af6766811add52cf7849dda7ea36e8e164c. Counts are not production or conversation-quality scores.

## What sold data can actually establish

The county's public parcel geometry and assessor characteristics are identity/context sources. An assessment is not the amount paid. Recorder documents can corroborate a transfer, its type, and encumbrances; recording date is not necessarily closing or contract date. The county states that documentary transfer tax is rounded by $500 increments and excludes assumed loans from its base. Consequently, dividing tax by a rate does not recover an exact total purchase price. [1–4]

An official 2021 county fee schedule lists a Sales Transfer Journal and separate property-characteristics products. Its historical $450 journal figure is not a verified 2026 quote, a purchased file, proof of exact price fields, or permission for redistribution. Before procurement obtain a current schema, sample, date coverage, refresh delay, correction policy, transaction types, APN history, price/consideration definition, and license. A journal alone may not supply concessions, interiors, contract dates, market exposure or completed renovation condition. [4]

MetroList is a relevant local MLS source; CRMLS also publishes sold-data access information. Public website display, IDX, registered VOW and internal analytical use are different licensing questions. A public page or agent login does not automatically authorize bulk extraction, model training, redistribution, photos, or retaining sold records indefinitely. Confirm San Joaquin coverage and permitted internal valuation use directly in the applicable agreement. RESO standardizes fields; it does not grant data access. [5–8]

For a closed sale retain canonical property/APN, transaction/document and listing IDs, county, property type, contract/close/recorded/publication dates, exact consideration, financing/concessions and sale type. Keep source snapshot hashes, permitted-use evidence and review identity. Flag non-arm's-length, partial interests, portfolio allocations, nominal consideration, family/entity transfers, auctions, foreclosure, lease and new-construction incentives. Some distressed sales can be appropriate comparisons with market/condition analysis; do not categorically pretend every foreclosure is worthless evidence. Deduplicate one transaction across providers and merged/split APNs. [1,2,8,9]

No independently audited, current parcel-level local closed-sale cohort was acquired in this pass. The earlier 15 tax-notice candidates remain research candidates, not 15 verified deals. Their notices require current redemption/title/status review. Do not backfill missing sold prices with asking prices, tax values, transfer-tax inversions or an AVM.

## Valuation and offer specification

Use competitive market, legal property type, lot/area, condition, quality and buyer utility rather than a fixed radius alone. Prefer suitable recent closed transactions; document why older or more distant evidence is better where applicable. Fannie Mae asks for at least three closed comparisons and supports market-based adjustments, not universal dollar-per-square-foot adjustments. Its guide does not set a universal net/gross adjustment ceiling. Bob's 30% gross adjustment review threshold, distance bounds and 25% candidate area band are internal screening choices, not appraisal rules. [9,10]

Analyze time changes between each comp's contract date and the valuation date. A flat annual county index does not establish a zero adjustment for every neighborhood/month. Concession adjustment is the market's price effect, not automatically the dollars the seller paid. Record evidence even for a supported zero. Do not optimize adjustments after reading a held-out target's price. [10]

As-is valuation and ARV are different estimands. ARV needs a defined scope, legal finished area/units, condition/quality assumptions, completion horizon and matching post-repair comparables. A sale of an unrenovated house cannot validate a renovated prediction. A completed renovation followed by sale can provide outcome evidence, but the sale remains a noisy value proxy influenced by timing, exposure and terms. A one-day valuation and a resale many months later should not be scored as the same question. Document horizon and market changes.

The 70% calculation remains a screening heuristic. A releaseable offer additionally requires repair line items and contingency, financing/draws/points, holding duration, utilities, post-acquisition taxes and supplemental bills, insurance/deductibles, HOA, title/escrow, commissions/concessions, exit costs, current payoffs, occupancy and margin. Unknown costs must block investment approval rather than become zero. BOE explains why an ownership change or new construction can create supplemental bills beyond the annual bill. [11]

Check actual permit jurisdiction and finaled permits rather than postal city. Treat ADUs, manufactured homes, condos, acreage, mixed-use and two-to-four-unit properties as separate markets and legal reviews. HCD's March 2026 ADU handbook includes 2026 changes; that is not approval for a specific garage conversion. Review leases and state/local tenant constraints, not assumed vacant possession. Obtain parcel-specific flood/fire and bindable insurance evidence; map proximity is not a policy quote or hazard clearance. DRE's 2026 law collection is a starting index for transaction-specific licensing/disclosure review, not automatic approval of contracts, agency, assignments or foreclosure solicitation. [12–15]

## Local accuracy acceptance

The executable protocol is documented in LOCAL-SALES-BENCHMARK.md. It keeps requests and outcomes separate, checks precontract prediction cutoffs, rejects future comps, duplicate target properties/transactions and inconsistent renovation outcomes, and reports abstentions. Supplied hashes/attestations do not independently authenticate documents or prove that an analyst did not know the target. A dataset with a valid schema is still not an audited cohort.

Freeze eligible sampling rules, raw data hashes, subject features, comp-selection/adjustment method, source availability vintage, policy/model commit and acceptance thresholds before opening outcomes. Use chronological development, calibration and final untouched evaluation periods. Keep repeat parcel and renovation-project groups together when splitting learned models; revise forecasts prospectively rather than rerunning a lucky seed. Rank comp candidates without the target sale. Use a separate appraiser/reviewer sample for source and condition correctness. Preserve failures, exclusions and abstentions.

Report as-is and ARV separately, each by city/competitive market, type, price band, condition, transaction age and forecast horizon. Include predicted/eligible counts, MAE dollars, median/mean/p90 percentage errors, signed bias, within-10% count and large overvaluation cases. Comp minimum/maximum is an observed span, not a calibrated confidence interval. Report false negatives on abstained opportunities as well as errors on priced ones. Small strata do not inherit a countywide grade.

Proposed project acceptance targets, not professional standards or achieved results: assemble at least 1,000 independent local outcomes across development and final evaluation; reserve at least 200 untouched outcomes for each intended production purpose before grading that purpose. An initial target is median APE <=5%, p90 APE <=15%, absolute mean signed error <=3%, plus a dollar-loss limit chosen from actual capital/risk policy. Report confidence/sampling uncertainty and abstention coverage; do not declare readiness just because these averages pass. Unsupported types/areas remain review-only. Renovated ARV cohorts may be much smaller; if adequate scope-matched outcomes are unavailable, ARV stays ungraded.

## Actual communication acceptance

Sold-sale data is not needed to test message delivery. Use explicitly approved test leads, numbers and mailboxes with isolated tenant records and truthful fixture labels. Never contact real tax-notice owners to manufacture a test set. Discovery, ownership, phone enrichment, contact permission and quote authority are distinct records.

The FCC's AI-voice ruling places generated voices within TCPA artificial/prerecorded-voice restrictions. Keep explicit business AI identity and the server's current consent/DNC/channel permission checks. SignalWire's current 10DLC materials require brand/campaign/number approval and documented opt-in for the applicable messaging use case; campaign approval is not recipient consent. Preserve text/version/time/source of consent and all later revocations. [16,17]

Regulatory freshness is a release gate: a September 30, 2026 FCC release announces new consent-revocation action. The full adopted order/effective provisions could not be retrieved in this environment; do not present the earlier January 2027 waiver summary as the definitive current rule. Keep broad immediate suppression as the product policy pending current applicable legal review. Do not weaken existing STOP protections based on a draft, press release, blog, or supposed exception. The project also requires recording/transcription-retention and California confidential-communication review. Existing AI disclosure is not by itself recording consent. [18]

For commercial email, check accurate identity/headers/subject, a valid postal address, clear advertising/opt-out information, an operable opt-out mechanism and suppression. FTC guidance requires honoring opt-outs within ten business days and keeping the mechanism usable for at least thirty days. The system's immediate suppression policy is stricter. A normalized inbound email adapter needs actual sender/transport authentication and a configured receiving domain, not trust in a payload's sender_verified flag alone. [19]

Trace intent → provider request → provider identifier → durable receipt → canonical source record → dashboard projection. Accepted/queued/sent/delivered/replied are separate facts. SignalWire says callbacks are best-effort and recommends REST confirmation/reconciliation. Its delivered SMS state confirms receipt at the end carrier network, not reading by a human. SendGrid delivered means receiving-server acceptance; opens/clicks can be machine activity and never prove seller identity or agreement. Use stable event IDs and raw-body signature checks; persist before acknowledging; tolerate replay, missing callbacks, reordered events and DB outages. Never automatically resend an uncertain accepted request. [20–23]

Source inspection found unresolved implementation work: REI backend/api/routes/sms_status.py catches failed database updates and returns 204; it directly overwrites delivery status. backend/api/routes/email_webhook.py helpers catch failed database persistence and the outer webhook returns 200. Those paths lack demonstrated durable provider-event replay/reconciliation, can acknowledge lost writes, and need tenant/destination/message binding review. The durable ordinary-reply resumption implementation does not close this separate status-event gap. No provider status callback fix is claimed by the new valuation benchmark.

## Scheduling and conversation acceptance

The implemented source reservation and its dashboard projection are internal operational facts. Choose and configure the actual external calendar/provider before claiming external synchronization. Required contract: exact IANA timezone, date and offset; resource/owner; duration; business/quiet hours; travel/buffer time; accessibility/language needs; current consent; canonical lead/address; atomic local reservation; stable external event identity; write receipt and read-back; cancellation and reschedule version checks. Free/busy lookup alone does not atomically reserve a slot against other writers.

For Google Calendar, a caller-supplied valid event ID supports lost-response duplicate recovery; conditional changes use etags/If-Match and can fail with 412. Insertion has separate identity semantics. No adapter is implied by this documentation. Test double bookings, two concurrent callers, recurring/all-day events, busy overrides, expired OAuth, 429/5xx, timeout after commit, manual edits, deleted events, DST nonexistent/ambiguous times and cancellation racing reminders. Display queued, internally reserved, externally confirmed and failed states distinctly. [24,25]

Keep Pipecat/SignalWire as the existing transport while testing turn behavior; adopting another framework does not certify quality. LiveKit's turn guidance is useful for semantic endpointing, interruption/backchannel differentiation and timing. Build consented recordings across quiet/noisy/poor connections, speech rates/accents, Spanish/code-switching, silence, corrections, emotional disclosures, wrong numbers, voicemails and hostile/prompt-injection text. A reviewer grades disclosure, factual grounding, listening, task completion, pricing limits, stop handling and graceful escalation independently of the generating model. Record STT errors, endpoint delay, first-audio latency, interruption cut-off and tool receipt timing. No synthetic transcript score can establish natural audio quality. [26]

## Release gates and required evidence

| Gate | Present state | Completion evidence |
|---|---|---|
| Exact code deployment | Merged source verified; running backend not verified | Served commit/build IDs across all services and matching dashboard API origins |
| Existing shared database | Disposable schemas tested | Actual baseline, reviewed migration order through 20261019, preserved records, restore/rollback rehearsal |
| Suppression/workflow journals | Local persistence/recovery code tested | Private durable mounts; power-loss/redeploy retention; tested single-writer or shared consistency design |
| Replica safety | Not accepted | Cross-replica STOP visibility and leased recovery races; no independent unshared journals for outbound replicas |
| Licensed data | Not acquired | Applicable executed rights, raw snapshots, independently reviewed closed transactions and condition evidence |
| Local valuation | Ungraded | Frozen, untouched, time-valid local cohort; stratified errors, abstentions and independent source review |
| Provider event history | Implementation gap | Durable canonical-message-bound intake, monotonic projection, replay and reconciliation after missed callbacks |
| SMS/voice account | Access not available here | Correct number/campaign/webhooks/signatures, opt-in/DNC evidence and approved-destination provider tests |
| Email identity/replies | Adapter contract implemented; routing not verified | SPF/DKIM/DMARC and verified sender; domain/MX adapter; signed events; reply authentication and opt-out drills |
| External calendar | Not established | Correct provider permissions, conflict/identity/version handling, create/read/cancel/reschedule receipts |
| Human conversation quality | Not graded | Consented actual audio set, independent rubric, traces and zero critical policy failures |
| Operational controls | Some source recovery exists | Tested kill switch, incident owner, queue ages/dead letters, rate/spend caps, alert routing and audit retention |
| Backup and recovery | No live drill | Database plus separate audio/object/journal backups; measured RPO/RTO and restored-source/dashboard consistency |
| Bounded autonomy | Not approved by evidence | Explicit scope/time/budget/contact/price policy, staged pilot, exception queue and rollback criteria |

Supabase database backups exclude Storage API object contents. Back up recordings/documents/journals separately and restore a representative whole workflow, not just an empty schema. Railway volumes provide persistence; their documentation is not proof that this application's mounts/topology are correct. [27,28]

A useful pilot order is read-only source reconciliation, approved internal test destinations, inbound handling, bounded consented follow-up, and only then narrowly authorized unattended actions. Proposed acceptance workload: 1,000 isolated workflow/fault cases plus a separate consented actual-audio/provider set and a multi-day monitored pilot. A thousand repeated fixtures are not a thousand live conversations. Stop expansion on any unauthorized contact, wrong-property quote, lost opt-out, duplicate uncertain send, false booking claim or unresolved production data loss. These are proposed acceptance criteria, not completed tests or a scheduled automation.

## Exact access still needed

Provide or connect the actual backend and dashboard deployment/project, a staging clone of the real database baseline, mounted-volume configuration, provider account access via the deployment secret store, the chosen external calendar/resource, approved test destinations and a licensed local sold-sale export with condition/scope evidence. Do not paste secrets into source, reports, chats or public PRs. Public listing research cannot substitute for these inputs. A test calendar invitation is still a communication to a person; use only approved test recipients.

## Primary-source register

1. County property information: https://www.sjgov.org/department/assessor/property-information/homeowners
2. County transfer tax: https://www.sjgov.org/department/assessor/recorder-county-clerk-information/recorder/documentary-transfer-tax
3. County Recorder: https://www.sjgov.org/department/assessor/recorder-county-clerk-information/recorder
4. Historical county fee schedule, explicitly dated 2021: https://www.sjgov.org/docs/default-source/assessor-county-clerk-documents/asr-fees-updated-110921.pdf?sfvrsn=e34b8614_1
5. MetroList: https://www.metrolist.com/about-us
6. MetroList rules: https://prospector.metrolist.net/documents/mls_rules/MLS_Rules.pdf
7. CRMLS IDX scope: https://go.crmls.org/idx-resources/
8. RESO: https://www.reso.org/data-dictionary/
9. Fannie Mae comparables: https://selling-guide.fanniemae.com/sel/b4-1.3-08/comparable-sales
10. Fannie Mae adjustments: https://selling-guide.fanniemae.com/sel/b4-1.3-09/adjustments-comparable-sales
11. BOE supplemental assessment: https://www.boe.ca.gov/proptaxes/supplemental-assessment/
12. HCD ADU handbook: https://www.hcd.ca.gov/building-standards/adu/handbook
13. California tenant guidance: https://oag.ca.gov/tenants
14. California insurance/flood guidance: https://www.insurance.ca.gov/01-consumers/140-catastrophes/FloodFacts.cfm
15. DRE 2026 law collection: https://www.dre.ca.gov/Publications/RealEstateLaw.html
16. FCC AI voice ruling: https://www.fcc.gov/document/fcc-confirms-tcpa-applies-ai-technologies-generate-human-voices
17. SignalWire 10DLC: https://signalwire.com/resources/guide/10dlc
18. FCC September 30 release (indexed; full PDF retrieval denied): https://docs.fcc.gov/public/attachments/DOC-425498A1.pdf
19. FTC CAN-SPAM: https://www.ftc.gov/business-guidance/resources/can-spam-act-compliance-guide-business
20. SignalWire webhooks: https://signalwire.com/docs/compatibility-api/guides/webhooks
21. SignalWire callback reliability: https://signalwire.com/docs/platform/webhooks
22. SendGrid event definitions: https://www.twilio.com/docs/sendgrid/for-developers/tracking-events/event
23. SendGrid webhook security: https://www.twilio.com/docs/sendgrid/for-developers/tracking-events/getting-started-event-webhook-security-features
24. Google Calendar creation: https://developers.google.com/workspace/calendar/api/guides/create-events
25. Google Calendar conditional versions: https://developers.google.com/workspace/calendar/api/guides/version-resources
26. LiveKit turn guidance: https://docs.livekit.io/agents/logic/turns/
27. Supabase backups: https://supabase.com/docs/guides/platform/backups
28. Railway volumes: https://docs.railway.com/volumes

Direct California statutory pages for Penal Code 632 and BPC 17941 were inaccessible to the research tool. No current statutory interpretation or comprehensive legal clearance is claimed. Indexed FCC items and historical fee schedules are labeled as such rather than promoted to full current-document verification. This source list is not evidence that every linked site's entire corpus was read.
