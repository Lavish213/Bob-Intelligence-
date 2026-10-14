# California research and acceptance — 2026-10-14 UTC

Research improves evidence handling, not autonomous appraisal authority. This pass covers practical source selection and investment underwriting. It does not establish exhaustive California knowledge, a county-trained model, universal website access, or live deployment acceptance.

## Verified county data

The July 6, 2026 official parcel export contains 252,652 unique APNs and boundaries, with no home features or sold prices. A separate official service sample of 1,000 positive-living-area parcels validates attribute parsing; it is geographically biased, not a random housing sample. Bedrooms and bath fields are unknown for 211 sample rows, assessment components for four. Unknown attributes remain unknown. Assessments do not become ARV. Detailed hashes and fields are in SAN-JOAQUIN-SOURCE-AUDIT-20261014.json.

The saved FHFA/FRED county series contains 51 annual observations, 1975–2025. It is a revised, developmental all-transactions index that includes refinance appraisals. Its 2026 vintage cannot be used as information available in a historical backtest. County trend ratios do not authorize individual property adjustments. No parcel-level historical market sale archive was acquired.

The official delinquency notice provides public-record research candidates, not verified current distress or interested sellers. SAN-JOAQUIN-LEAD-SAMPLE-20261014.json documents a small real-source sample checked against parcel attributes. No owner contact information was retained. No ARV or offer is invented where reviewed closed sales and condition evidence are absent. The auction page currently gives the next sale date as TBD; historical auction results are not ordinary arm’s-length comps.

## Source roles and access

| Source | Useful evidence | Required handling |
| --- | --- | --- |
| County GIS/Assessor | APN, boundaries, physical/tax context | Preserve APN zeroes; verify identity and missing fields; postal city is not permit jurisdiction |
| Treasurer notices/auction | Dated tax-default/auction records | Recheck redemption and current status; no seller intent, contact permission or market value inferred |
| Recorder/title provider | Transfers, liens, easements | Verify transaction type, consideration and current title/payoffs; transfer tax cannot identify an exact price |
| Licensed MLS/RESO feed | Listing history and closed transactions | Contract/credentials required; distinguish sale versus lease, ClosePrice versus ListPrice, availability vintage and duplicates |
| Propwire/provider exports | Candidate discovery/enrichment | Verify export freshness and provenance; no assumption that imported phone is permission |
| Consumer listing portals | Leads and corroborating listing context | Do not claim universal crawler coverage; respect provider access; asking price is not sold comp |
| FHFA/FRED/CAR aggregates | Market-cycle context | No individual ARV or automatic time adjustment from broad county data |
| Permit authority/HCD | Legal area, units, ADU process | Actual city/county jurisdiction, permit/inspection status and scope required |
| CAL FIRE/FEMA/CDI | Hazard and insurance review | Map context is not a bindable insurance quote or parcel clearance |

San Joaquin's eight cities are Escalon, Lathrop, Lodi, Manteca, Mountain House, Ripon, Stockton and Tracy. Mountain House incorporated in 2024; Modesto and Turlock are outside this county. Rural Delta, agricultural, condominium, manufactured, acreage and detached urban properties need separate comparable markets.

## Underwriting workflow

1. Bind source evidence to the canonical property and dated lead; deduplicate by property and transaction, not just address or listing ID.
2. Treat expired/withdrawn/reduced listings as possible leads. A price-change timestamp alone does not prove a reduction. Verified county and residential sale classification are required.
3. Review independent closed sales of the same competitive market and type. Keep source references, actual close price/date, publication availability, condition and adjustment rationale. Exclude leases, subject sales, duplicate transfers and unsupported comparisons.
4. Separate as-is value from after-repair value. A defined repair scope and post-repair comparable condition are essential to ARV. Appraisal and automated statistical research remain different evidence classes.
5. Itemize acquisition, repair contingency, financing, holding, taxes, insurance, utilities, HOA, title/escrow and exit costs. Missing costs are not zero. The 70% screen is a heuristic, not an offer approval. Existing cent-based flip/rental/mortgage math is supplemented with a bounded downside grid for resale declines, repair overruns and extra holding costs.
6. Rental NOI excludes debt service; cash flow subtracts debt and reserves. DSCR, cap rate and cash-on-cash are distinct. Actual leases, vacancy, concessions, operating costs and applicable tenancy rules govern assumptions; no automatic vacant possession or immediate market-rent reset.
7. Estimate tax from actual parcel TRA, direct assessments and possible supplemental reassessment. Existing low assessment is not next owner's full annual cost. Obtain property-specific insurance, including relevant flood/fire coverage and deductibles.
8. Verify title, liens, current payoffs, permits, legal units, utilities, access, hazards and occupancy before investment approval. Seller equity requires current debt/liens, not last sale price. Seller net proceeds differ from price and company profit.
9. Approved tool permissions and current offer policy control Sophia quoting. Bob context, public records and research results never grant dial/offer authority.

## Primary sources reviewed

- https://sjmap.org/GISDataDownload.htm
- https://sjmap.org/DistrictViewer/
- https://www.sjgov.org/docs/default-source/assessor-county-clerk-documents/assessor-fee-schedule.pdf
- https://www.sanjoaquin.gov/department/ttc/tax/general-tax/announcements
- https://www.sanjoaquin.gov/department/ttc/tax/redemption/public-auction
- https://fred.stlouisfed.org/series/ATNHPIUS06077A
- https://www.fhfa.gov/faqs/hpi
- https://www.boe.ca.gov/proptaxes/supplemental-assessment/
- https://www.hcd.ca.gov/building-standards/adu/handbook — March 2026 edition
- https://oag.ca.gov/tenants — state and local tenancy review
- https://www.insurance.ca.gov/01-consumers/140-catastrophes/FloodFacts.cfm
- https://osfm.fire.ca.gov/what-we-do/community-wildfire-preparedness-and-mitigation/fire-hazard-severity-zones
- https://www.dre.ca.gov/Publications/RealEstateLaw.html — 2026 law/reference resources
- https://dd.reso.org/DD2.1/Property/StandardStatus/
- https://www.ftc.gov/business-guidance/resources/qa-telemarketers-sellers-about-dnc-provisions-tsr-0

These are review inputs, not a legal opinion or proof of an individual parcel's status. Local rules and actual transaction facts must be checked when used.

## Measured acceptance and gaps

Bob: 3,439 Python tests pass, including 1,000 parcel cases and 1,000 independent integer-cent stress-ledger cases. Existing historical Ames accuracy remains approximately 6.60% mean absolute percentage error, custom grade B; it is Iowa, not California. No local accuracy grade is justified without a licensed/local sold-price cohort and dated features.

Source access barriers remain: MLS/provider credentials and export rights; current sold comps and inspection evidence; official sale journals/characteristics are paid products. No purchase, provider registration, seller contact or live migration occurred. Real-source candidate compilation does not equal a verified deal list. Live audio, delivery, calendars and hosted dashboard receipts require production acceptance evidence separately from synthetic regression tests.
