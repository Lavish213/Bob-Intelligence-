# Bob property valuation: methods, assumptions and implementation

Research and source implementation: 2026-10-14. This module computes investment research from supplied, reviewed records. It does not discover every source, independently authenticate MLS facts, inspect a house, issue an appraisal or authorize an offer. Price accuracy on real houses has not been demonstrated by synthetic unit tests.

## Separate the decisions

| Decision | Meaning | Bob treatment |
|---|---|---|
| As-is market indication | Current property's condition and market, on a stated date | Run sales comparison against the actual current features |
| After-repair value (ARV) | Conditional indication for specified completed repairs in the current market | A separate request using planned target features and an identified renovation scope; no automatic future appreciation |
| Investor purchase limit | Acquisition price compatible with a cost/profit scenario | Separate flip underwriting; never relabel as market value |
| Seller proceeds | Sale price less seller obligations, liens and transaction costs | Separate closing estimate, not the home's value |
| Asking price / pending contract | Marketing/negotiation evidence | Supporting information, never counted as an independent closed sale |
| Assessed value / automated estimate | Separate administrative or model output | Not substituted for missing sold evidence |

## Primary-source research

1. [Fannie Mae: comparable sales](https://selling-guide.fanniemae.com/sel/b4-1.3-08/comparable-sales). Competitive properties and location/physical/legal similarity matter. The guide specifies at least three closed comparables for its sales-comparison appraisal process. Recent sales are preferred, but an older, better match can be defensible with explanation. Bob adopts a conservative three-sale floor; this is not a claim that Bob performs a lender appraisal.
2. [Fannie Mae: adjustments](https://selling-guide.fanniemae.com/sel/b4-1.3-09/adjustments-comparable-sales). Adjustments need market evidence. Concession impact is not necessarily the seller's concession cost. Market-time analysis relates to contract timing and the valuation date. Bob therefore requires reviewed time/concession entries even for a zero adjustment. Final reconciliation remains within the reported adjusted-sale span.
3. [Fannie Mae: condition and quality](https://selling-guide.fanniemae.com/sel/b4-1.3-06/property-condition-and-quality-construction-improvements). Condition and quality describe each property on its own merits at the relevant time. Matching broad ratings alone need not mean identical market contribution. Bob requires a complete comparison-review reference, including factors outside its basic feature grid.
4. [Fannie Mae: unacceptable practices](https://selling-guide.fanniemae.com/sel/b4-1.1-04/unacceptable-appraisal-practices). Unsupported results/adjustments and inappropriate comparisons are unacceptable; protected-class and crime-based valuation reasoning is prohibited in the guide. Bob's numeric feature contract excludes demographic/crime variables and never targets a seller-requested price by deleting inconvenient sales.
5. [Fannie Mae: cost and income approaches](https://selling-guide.fanniemae.com/sel/b4-1.3-10/cost-and-income-approach-value). These approaches can corroborate an analysis where relevant. Neither is accepted by that guide as a standalone substitute for the required sales analysis. Rental evidence and suitable property context are required; a generic cap rate does not establish an owner-occupied home's market price.
6. [FHFA HPI FAQ](https://www.fhfa.gov/faqs/hpi). Repeat-sales indexes measure average price change and reduce changes in the property mix. They can support a reviewed time-adjustment analysis, not prove the same appreciation for every parcel. Do not apply a regional index automatically to a house's sale price or manufacture a future price forecast.
7. [CFPB: mortgage payment components](https://www.consumerfinance.gov/ask-cfpb/on-a-mortgage-whats-the-difference-between-my-principal-and-interest-payment-and-my-total-monthly-payment-en-1941/). Principal/interest is distinct from tax, insurance and possible mortgage insurance. HOA charges can be separate. Bob's fixed-rate payment function makes these inputs explicit rather than hiding them inside the loan payment.
8. [California BOE: change in ownership](https://www.boe.ca.gov/proptaxes/faqs/changeinownership.htm/). Acquisition/reassessment rules mean a seller's historical tax assessment is not a reliable current price shortcut. Use parcel-specific tax and assessment information when forecasting ownership costs; do not assume the old bill survives a purchase.

## Comparable-sales math

For each sale, **adjusted indication = closed sale price + signed market-supported adjustments**. Adjust the comparable toward the subject: an inferior comp generally needs a positive adjustment; a superior comp generally needs a negative adjustment. Apply that convention to a specifically reviewed market effect, not to guessed dollar amounts per bedroom.

The gross adjustment is the sum of absolute adjustment amounts; the net is their signed sum. Offsetting large changes can conceal an unreliable comparison if only the net is inspected. A zero time/concession adjustment still needs a source and reviewer. Concession effects are nonpositive, and may be zero when supported. Repairs are not automatically a dollar-for-dollar condition adjustment: cost and market contribution are different quantities.

Price per square foot is a diagnostic. Multiplying an average whole-property price per foot by subject area assumes away differences in land, condition, amenities, market and marginal area contribution. Paired-sales analysis should isolate the feature difference after reviewing other influences; regression or local index analysis needs sufficiently representative data and validation. Bob does not invent those coefficients. A human-reviewed evidence reference accompanies each applied adjustment.

Bob reconciles accepted adjusted sales with a deterministic engineering weight: `1 / (1 + sale_age_days/180 + distance_meters/2000 + relative_area_difference)`. It is a transparent research heuristic, not an appraisal standard or calibrated accuracy model. The interval is the observed minimum/maximum adjusted sale, not a statistical confidence interval. The module retains inconvenient values and requests review when dispersion is wide.

Default review policies are 365-day sale age, 5,000-meter distance, 30% gross adjustment and 20% adjusted-sale dispersion. These are software policies, **not universal lender limits or sufficient proof of comparability**. Missing features, unsupported differences, mismatched property types, duplicate sales/properties, subject-as-comp, future/unavailable records and unverified/nonmarket transactions do not silently become a price. Competing markets require an explicit review reference and location adjustment. An old valuation effective date cannot enter a current Bob brief after 30 days.

Beyond the basic grid, review legal use/tenure, permitted living area, ADU status, physical access and utility, year/effective age, layout, view, objective hazards/flood status, location influences, HOA/special assessments, owned versus leased solar, financing terms, and transaction history. The comparison-review reference attests that these relevant factors were evaluated; the software does not infer them from an address.

## Investment math implemented

| Function | Calculation and limits |
|---|---|
| `repairs_with_contingency` | Itemized cents subtotal plus explicit contingency basis points; scope, bids, permits and schedule must be supplied |
| `screening_mao` | ARV × multiplier − repairs; the default 70% is a configurable investor screen, not an appraisal or profit guarantee; it does not replace REI's legacy MAO contract |
| `flip_analysis` | Resale less purchase, repairs, buying/selling costs, holding and financing; solves a conservative purchase limit including purchase-price closing costs and target profit; checks final cent rounding |
| `rental_analysis` | Effective income after vacancy; NOI after operating costs; cash flow after debt/reserves; DSCR, cap rate and income indication kept distinct |
| `cash_on_cash_return` | Annual after-debt cash flow / initial equity; distinct from project-spend return or appreciation |
| `mortgage_payment` | Fully amortizing fixed-rate principal/interest, including a zero-rate case; explicit monthly tax/insurance/HOA/PMI additions |
| `cost_approach` | Land + replacement improvements − physical/functional/external depreciation; a corroborating indication |

Debt service and capital reserves are outside NOI in this investment model; neither mortgage principal repayment nor income-tax depreciation is an operating cost for this calculation. Operating inputs should include actual tax/insurance, HOA, maintenance, management and utilities as applicable. Do not count financing principal again when the full purchase price is already a project cost. Recompute financing/holding assumptions when price, leverage, duration or loan terms change. Borrowed money is not equity, and project-spend return is not cash-on-cash return.

For flip stress tests, use lower resale, longer holding, larger repair scope/contingency, higher selling costs and financing changes. As-is value is not simply ARV minus repairs. Liens affect seller proceeds/equity and a transaction's feasibility, not automatically the property's market value. Rent estimates, insurance quotes, tax reassessment and exit liquidity need evidence rather than optimistic constants.

## Synthetic worked example (not a real Stockton house)

Target: 1,800 square feet, 3 bedrooms, 2 bathrooms, reviewed renovated condition. All figures below are synthetic test inputs, including the adjustment evidence references.

| Comp | Sale | Living area adjustment | Concession market impact | Adjusted indication |
|---|---:|---:|---:|---:|
| A: 1,700 sqft | $450,000 | +$10,000 | $0 | $460,000 |
| B: 1,850 sqft | $465,000 | −$5,000 | $0 | $460,000 |
| C: 1,800 sqft | $462,000 | $0 | −$2,000 | $460,000 |

Here the supported indication is $460,000, conditional on the stated scope; a zero-width observed sale span still does not mean zero uncertainty. With $60,000 repairs, the 70% screen is $262,000. With 2% acquisition closing costs, $3,000 fixed acquisition costs, $6,000 holding, $10,000 financing, 6% selling costs and a $50,000 profit target, the detailed purchase limit is **$297,450.98**, under those fixed assumptions. At a $280,000 purchase, total project cost is $392,200 and modeled profit is $67,800. These are different investor scenarios, not seller offer approvals.

A separate synthetic rental example uses $30,000 annual rent, 5% vacancy, $9,000 operating costs, $14,400 annual debt and $2,400 reserves: NOI $19,500; cash flow $2,700; DSCR 1.354167. At a supported 6.5% cap-rate assumption, the income indication is $300,000, not proof of a sale price. A $300,000, 6%, 30-year fixed loan has $1,798.65 monthly principal/interest; add the independently supplied ownership charges.

## Bob → Sophia contract and deployment

`intel_packets.valuation_inputs` is an optional JSON column added by the idempotent migration `20261014_bob_valuation_inputs.sql`. Apply it once to the shared database before storing this new input. Existing source snapshots include the field, so valuation-only edits invalidate stale generation fingerprints. Only trusted operator/service ingestion should write reviewed records; seller speech and model arguments never attest to source verification or adjustment review.

The request's subject property must match the job's canonical lead/property binding. `generate_call_brief` computes and attaches `evidence.valuation`; missing/invalid inputs produce an explicit unavailable state. Cash amounts are integer cents; basis-point rates are integer inputs. Financial functions use Decimal, while comparable reconciliation uses exact rational weights to avoid intermediate rounding errors. Reports include per-sale prices/adjustments, source/review references, rejected input reasons and review flags. They never enable dialing, tool permissions or quote/offer authority.

Sophia accepts bounded current advisory reports for the same lead. Figures stay out of model guidance until identity and property facts are verified in the current call. Then the guidance labels them internal research, explicitly forbids quoting them as an offer, and retains the existing authorized offer tool. Loader rejection clears old valuation state, and the internal rendering ignores arbitrary source notes/instructions. A live conversation can change the property's facts; that needs review rather than automatic use of an old target-condition estimate.

Offline usage: `python -m backend.valuation reviewed-input.json`. For the input shape and hand-verified synthetic calculations, see `tests/test_valuation.py`. A generated report with `ready_advisory` means the supplied evidence passed these software checks; it does not establish source authenticity, real-world accuracy, live deployment or approved pricing. The legacy REI price-per-square-foot calculator and automatic source collectors are not replaced by this additive module.

Remaining: licensed/current sold-data adapters, authenticated review ingestion/UI, robust rehab/rent evidence, broader property-type modeling, completed shared-database baseline, out-of-time local backtesting and calibrated prediction intervals, real deployment/provider acceptance, and explicit pricing-approval workflows. Backtesting must use only evidence available at each historical valuation date and compare predictions to later independently observed outcomes using bias, absolute/percentage error, error by property segment, and range coverage.

## Validation evidence

The local source pass completed 308 Bob Python cases (71 added), 53 actual embedded PostgreSQL migration/contracts (2 added), 1,514 REI Python cases (24 added), and 11 cross-repository checks. The bridge test runs the actual Bob planner from a bound SQL snapshot and the actual Sophia loader/context, verifies dollars from integer cents, withholds research figures before current-call identity confirmation, and confirms that no offer permissions are created. Source lint passed. Valuation calculation coverage was 89% for the comparison engine and 97% for financial functions in this local run; subprocess CLI cases are tested but are not included by that in-process coverage measurement. These checks use synthetic sales/text and disposable SQL, not independently observed sale predictions or live phone audio.


The follow-up randomized and recorded-sale diagnostic is documented in `VALUATION-STRESS-AND-SALE-GRADING.md`. The review-only candidate shortlist improves the unadjusted historical diagnostic but does not establish current local appraisal/ARV accuracy. Exact rational reconciliation fixes a half-cent edge, and flip purchase limits now test the next cent explicitly.
