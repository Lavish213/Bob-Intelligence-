# San Joaquin calibration cohort — intake contract

This is the exact export to request, and the one command that turns it into a
benchmark cohort. It exists because "build a calibration cohort" was previously a
month of hand-authoring; it is now an export plus a bounded review pass.

Nothing here invents a sale, a condition, an adjustment or a price. Every row that
cannot be supported is rejected with a named reason and written to a rejects file.

## 1. What to ask the data provider for

One CSV of **closed, arm's-length residential sales in San Joaquin County**
(FIPS 06077). One row per sale. Every column is required; a missing column rejects
the whole file rather than defaulting.

### Sale identity and provenance
| Column | Meaning |
|---|---|
| `sale_id` | Unique identifier for the transaction |
| `apn` | Assessor parcel number — the canonical property key |
| `address`, `city` | For display and stratification |
| `latitude`, `longitude` | Decimal degrees; used for the distance screen |
| `market_area` | Competitive submarket label |
| `property_type` | One of `single_family`, `condo`, `townhouse`, `manufactured`, `two_to_four_units` |
| `source_ref` | Where the record came from |
| `source_sha256` | SHA-256 of the source document or extract |

### Transaction
| Column | Meaning |
|---|---|
| `contract_on`, `closed_on`, `available_on` | ISO dates; must be in that order. `available_on` is when the record became publicly knowable |
| `sale_price` | Dollars. Parsed to exact cents; a fractional cent rejects the row |
| `arms_length` | Must be true. Non-arm's-length rows are rejected, not down-weighted |

### Condition — the part most exports omit
| Column | Meaning |
|---|---|
| `condition_basis` | `unchanged_as_is` or `completed_renovation` |
| `condition_ref` | Evidence of the condition at sale. **Not inferable from price** |
| `condition_sha256` | SHA-256 of that evidence |
| `renovation_plan_ref`, `completed_on` | Required when `completed_renovation`, and must predate contract. Must be empty otherwise |

An ARV cohort is impossible without `completed_renovation` rows. This is the single
column most likely to be missing from a standard export, so ask for it explicitly.

### Features, as observed before the sale
`features_observed_on`, plus `living_area_sqft`, `bedrooms`,
`bathrooms_half_units`, `lot_sqft`, `garage_spaces`, `pool`, `condition`, `quality`.

`features_observed_on` must precede the prediction date, or the case is dropped for
using information that did not exist yet.

## 2. Build the cohort

```
python scripts/build_san_joaquin_cohort.py sales.csv \
  --out cohort.json --review-queue review.json --rejects rejects.json \
  --evaluated-on 2026-11-08 \
  --cohort-ref  "sjcounty:export-2026-11" \
  --rights-ref  "contract:your-data-licence" \
  --selection-ref "policy:how-rows-were-selected"
```

Defaults match the engine's shipped screening policy: 180-day comp age, 800 m
radius, 25% living-area band, 3 to 6 comps per case, prediction one day before
contract. All are flags.

### What it guarantees

- **No leakage.** A comparable may only be used if it both closed and became
  available on or before the prediction date. The benchmark validator re-checks
  this independently, so the two must agree.
- **No self-reference.** A sale is never its own comparable, and a parcel appearing
  twice is dropped rather than inflating the cohort.
- **Reproducible.** Two runs over the same export are byte-identical, and the
  cohort records the SHA-256 of the export it came from.

## 3. Review pass — the irreducible human work

The builder emits a **skeleton**: comparables selected, adjustments empty. It
cannot fill them, because a market-supported adjustment is a judgement with
evidence behind it, and inventing one would corrupt the very number the cohort
exists to measure.

`review.json` lists, for every comparable, exactly which adjustment categories are
required and why. For each one a reviewer supplies `amount_cents`, `evidence_ref`
and `reviewed_by`, plus a `comparison_review_ref` per comparable.

Until then the cohort evaluates to **zero predictions and all abstentions** —
which is the honest state, not a failure.

## 4. Score it

```
python scripts/benchmark_san_joaquin.py cohort.json \
  --expected-sha256 <sha256 of cohort.json> --evaluated-on 2026-11-08
```

Output carries MAE, mean/median/p90 absolute percentage error, signed bias,
within-10% count, observed comp-span hit count, and the IAAO ratio study: median,
mean and weighted mean ratio, COD, PRD, PRB, with flags against the residential
bands (COD ≤ 15, PRD 0.98–1.03, median ratio 0.95–1.05, PRB within ±0.05).

Results are stratified by purpose, city and property type.

## 5. What a score still does not prove

Checksums and attestations do not independently verify a sale, a condition, the
rights to use the data, or freedom from analyst hindsight in hand-authored
adjustments. A sale price is an imperfect proxy for value. The comp span is an
observed range, not a statistical interval — and on a pipeline run of 58 synthetic
cases its hit rate came out at 70.7% against the 70.8% predicted by the
`(n-1)/(n+1)` order-statistic law for the mean comp count, which is the cap that
motivates replacing it with conformal intervals once a real calibration set exists.

A small or unrepresentative cohort cannot justify a countywide conclusion.
