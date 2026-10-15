# Frozen local sale evaluation contract

Run from the Bob repository:

```bash
python scripts/benchmark_san_joaquin.py /private/cohort.json --expected-sha256 EXACT_RAW_FILE_SHA256 --evaluated-on YYYY-MM-DD
```

Output goes to stdout; malformed data or a raw checksum mismatch exits 2 with invalid_input. Keep licensed source files and results in approved private storage, not the public repository. Maximum input is 10 MB/10,000 cases/50 comparables per request. The CLI performs no provider requests, database writes, contact, quote authorization or deployment. Dates are calendar dates, so intraday availability is intentionally unsupported; use a conservative next-day publication date where needed.

The top-level object has exactly schema_version="1.0", dataset_kind (synthetic or attested_local_sales), cohort_ref, rights_ref, selection_ref, and cases. Every reference object has exactly source_ref (bounded source identifier) and sha256 (64 lower-case hexadecimal characters). Hashes are supplied evidence locators, not digital signatures or independent verification. attested_local_sales is a declared evidence class, not a verified-data badge.

Every case has exactly case_id, city (bounded identifier), county_fips="06077", geography_ref, features_observed_on, request, truth. One property and one target transaction may appear only once per cohort. The geography evidence must independently establish canonical subject identity; this field is an attestation and the code does not query a county map. Comparable competitive-market/type/source/condition restrictions remain the existing valuation engine's responsibility; audit the input attestations separately.

request is the existing compare_sales input: as_of, purpose (as_is or after_repair), subject, comparables, optional policy, and renovation_plan_ref for after_repair. subject contains exactly property_id, market_area, property_type, features. All eight features are mandatory: living_area_sqft, bedrooms, bathrooms_half_units, lot_sqft, garage_spaces, pool, condition, quality. Subject features must be observable by as_of. Comps retain exact integer sale_price_cents, closed_on/contract_on/available_on, independent property/sale IDs, source_ref, arms_length/verified attestations, comparison_review_ref, type/market, distance_meters, full features and evidenced adjustments. Missing/time/concession adjustment evidence does not become zero automatically.

truth has exactly:

| Field | Requirement |
|---|---|
| property_id | Same canonical subject property |
| sale_id | Unique target transaction; never a comp sale |
| kind | closed_sale; assessments and asking prices rejected |
| price_cents | Positive bounded integer; booleans/floats rejected |
| contract_on | Strictly after the prediction date |
| closed_on | On/after contract and within 90 days after prediction |
| available_on | On/after close and no later than evaluated-on |
| arms_length | Literal true attestation |
| sale_ref | Source reference plus document hash |
| condition_basis | unchanged_as_is or completed_renovation |
| condition_ref | Evidence of outcome condition and scope, not assumed from price |
| renovation_plan_ref | null for as-is; exact request plan identifier for ARV |
| completed_on | null for as-is; after prediction and on/before target contract for ARV |

The 90-day horizon is a deliberately narrow benchmark policy, not an appraisal rule or adequate horizon for every renovation. Longer projects need a separately defined prospective outcome/market-change protocol; do not quietly widen this test after seeing results. As-is cases need evidence that no material renovation changed condition before sale. ARV cases need completion evidence matching the forecast scope. A contract price influenced by financing/marketing/exposure is still an imperfect value label.

All cases are validated before the predictor runs. Future comps, wrong-region targets, self comparisons, duplicate targets, future labels, unknown target kinds and incompatible condition claims reject the whole dataset rather than disappear from a score. The predictor receives a copy of request only; changing that copy invalidates the run. Raw file hash, canonical dataset hash and per-request hashes support reproducibility. They cannot detect arbitrary hindsight in hand-authored adjustments or dishonest supplied provenance. Commit/environment IDs, independent source audit and sealed outcomes are external acceptance requirements.

The report keeps eligible/predicted/abstained counts and statuses; calculates MAE dollars, mean/median/p90 APE, signed percentage bias, within-10% count and observed comp-span hit count; and separates purpose/city/type. p90 uses the nearest-rank definition. No error metric is computed for abstentions. They remain in the eligible denominator. Add price/condition/horizon strata and uncertainty analysis in the independent cohort report; the current runner does not claim a complete statistical certification. A small cohort or unrepresentative sample cannot justify a countywide conclusion.

Every result has production_ready=false, quote_authorized=false and offer_authorized=false. A successful schema/metrics run never grants operational authority. Synthetic output says synthetic_contract_only. Supplied local attestations output attested_local_evaluation_requires_source_audit. The fixture in tests/test_local_benchmark.py is explicitly synthetic and is not a real Stockton sale. Its 1,000 seeded randomized price trials verify arithmetic and isolation, not San Joaquin predictive accuracy or a trained model.
