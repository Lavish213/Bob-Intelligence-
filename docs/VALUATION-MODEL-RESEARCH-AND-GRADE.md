# Bob richer valuation research and grading — 2026-10-14

The earlier unadjusted comp diagnostic was too weak for automatic pricing. This pass studies public assessor projects, adds a research model that learns nonlinear and regularized relationships from richer physical data, and evaluates 1,124 distinct later sales. The historical research mean error improves into the project's B band; live California pricing and completed-scope ARV remain unvalidated.

## Projects, reports and implementation lessons

| Primary project/report | What was examined | Applied lesson |
|---|---|---|
| [Cook County residential AVM](https://github.com/ccao-data/model-res-avm/tree/feec9b79229e5ea9cfcbe042184855c2e047ae14) | Published model-selection rationale, rolling-origin validation, feature engineering, extreme-property issues, output reports | Compare regularized and boosted models; separate tuning from later-sale scoring; report tails rather than only averages |
| [Cook County condominium AVM](https://github.com/ccao-data/model-condo-avm/tree/5a673fd37e70dd38c56286785aa57e76177defbb) | Dedicated condominium modeling workflow | Keep property types separate; do not apply a detached-house model to condos or multi-unit properties |
| [Cook County sales validation](https://github.com/ccao-data/model-sales-val) | Geographic/time/property grouping and transaction anomaly review | Transaction validation precedes valuation; statistical anomalies prompt investigation rather than prove nonmarket status |
| [Tidy Modeling with R: resampling](https://www.tmwr.org/resampling) and [Ames workflow](https://www.tmwr.org/ames) | Apparent training accuracy versus held-out accuracy, reproducible preprocessing, property attributes | Fit preprocessing only on fitting data; hold target parcels and labels out of fitting and calibration |
| [IAAO published AVM standard, revised July 2018](https://researchexchange.iaao.org/jptaa/vol15/iss2/5/) | Published scope and guidance on AVM development and use | An AVM is a governed data/model process; a benchmark score alone does not certify an appraisal |
| [scikit-learn leakage guidance](https://scikit-learn.org/stable/common_pitfalls.html), [LightGBM features](https://lightgbm.readthedocs.io/en/stable/Features.html), [CatBoost overfitting detector](https://catboost.ai/docs/en/concepts/overfitting-detector) | Training-only transforms, categorical handling and validation controls | Use a feature whitelist, missing-data transforms inside fitting pipelines, and explicit calibration separation |

These are established public assessor projects and primary technical sources, not a ranking by GitHub stars. The implementation is original; no assessor source code is copied. Cook County reports that LightGBM was selected after comparison with alternatives and uses time-based validation. Its model also documents ongoing data-quality and extreme-property weaknesses. Bob adopts the comparison discipline, not a claim that Cook County accuracy transfers to Iowa or California. The IAAO source listed here is the published 2018 standard; this work does not assert certification against any newer standard.

## Root cause of the previous weak result

The prior numeric diagnostic averaged raw sale prices after feature-based selection. It deliberately did not invent reviewed dollar adjustments, so differences in condition, quality, age, basement finish and layout remained in the price signal. Selection improved it, but unadjusted prices are not enough. Adding a universal price-per-square-foot multiplier would not solve omitted features or market-specific marginal effects.

The new `backend/valuation/market_research.py` learns log sale price from 74 whitelisted physical/location attributes: living and basement areas, condition/quality ratings, construction/remodel years, structure/style, utilities, garage, finishes, rooms, lot dimensions, outdoor amenities and neighborhood. Sale price, parcel ID, row order, sale-condition/type, sale year/month, seller asking price, demographic and crime inputs are not predictors. The source's monetary `Misc Val` field is also excluded. Target rows' prices are revealed only for scoring; they never enter feature transformation or estimation.

Three fixed models are compared: Ridge with alpha 20; LightGBM with 900 trees, 15 leaves, minimum leaf sample 15, learning rate 0.03 and L2 regularization 5; CatBoost with 900 iterations, depth 6, learning rate 0.04 and L2 regularization 8. The ensemble equally averages their log predictions. It is a research indication of typical conditional price, not an unbiased arithmetic-mean sale-price estimate or an appraisal. Parameters and weights are not optimized against the target years. No test-year early stopping is used.

## Recorded-sale protocol and result

The checksum-pinned primary [Ames assessor-origin dataset](https://jse.amstat.org/v19n3/decock/AmesHousing.txt) contains 2,930 residential sales. A prespecified detached-house/normal-warranty-deed filter retains 1,943 records. No target is removed because its sale price or prediction error is inconvenient.

Each annual model is frozen at January 1. Source sale months are assigned month-end closing and an assumed 30-day availability lag; records that do not meet that cutoff are excluded from training. The latest 15% of earlier eligible records form disjoint calibration data. The remainder alone fits the estimators, imputation, scaling and category encoding. A target parcel cannot overlap fitting or calibration. No fitting is performed after calibration.

| Year | Fitting records | Calibration records | Distinct sale targets | Ensemble median absolute error | Ensemble mean absolute error | Mean dollar error |
|---|---:|---:|---:|---:|---:|---:|
| 2008 | 680 | 120 | 432 | 4.4282% | 6.6075% | $10,954.09 |
| 2009 | 1,049 | 186 | 466 | 4.4345% | 6.5341% | $11,196.35 |
| 2010 | 1,446 | 256 | 226 | 5.0444% | 6.7317% | $11,909.41 |
| All targets | — | — | **1,124** | **4.5290%** | **6.6020%** | **$11,246.61** |

There are 4,496 model-versus-sale comparisons across the four alternatives, representing 1,124 distinct target homes, not 4,496 independent homes. The complete JSON report includes every model family, quality segments, dependency versions, code/data-bound artifact identifiers, exclusions, review flags, per-year feature importance and worst examples.

For a fair before/after comparison, both methods are also scored on exactly the same subjects where the original shortlist had at least three candidates. These paired cohorts total 1,049 houses. On the **same 215 houses in 2010**:

| Measure | Previous unadjusted shortlist | New research ensemble |
|---|---:|---:|
| Mean dollar error | $22,881.36 | $11,580.50 |
| Median absolute percentage error | 9.8563% | 4.8372% |
| Mean absolute percentage error | 13.2455% | 6.6517% |
| Within 10% of recorded sale | 110/215 | 176/215 |
| Misses greater than 20% | 48/215 | 8/215 |
| Worst absolute percentage error | 131.5722% | 39.5918% |

That is about a 49.4% reduction in mean dollar error on the identical 2010 cohort. The error rubric remains the previous project policy: A ≤5%, B ≤10%, C ≤15%, D ≤20%, F >20% absolute error. The overall 6.6020% mean and paired 6.6517% mean fall in B, not A. Across all years, 598 targets are within 5%, 306 are between 5% and 10%, and 51 still miss by more than 20%. The largest overall miss remains 126.8358%. These failures remain in the score even when a research guard withholds a displayed number.

## Uncertainty and review controls

The latest earlier calibration records provide a finite-sample 90% quantile of absolute log-price residuals. It defines a multiplicative residual band. This is not the old observed-comp span. Temporal exchangeability and archived source availability are not established, so a nominal 90% label is not a coverage guarantee. Empirical coverage is 90.9722% in 2008, 86.4807% in 2009 and 89.8230% in 2010, or 88.8790% overall. The undercoverage is reported rather than hidden or corrected using the target outcomes.

Research output is withheld for a different region, stale cutoff, unsupported property type, missing essential features, unseen neighborhood, essential numeric features outside the fitting sample's support, future construction metadata, or more than 15% disagreement among model indications. The 15% threshold and 365-day age limit are engineering review policies, not universal appraisal rules. Cheap scope checks run before expensive predictions; an unsupported extreme record cannot break a valid batch. Numeric benchmark scoring still includes every target, preventing these guards from inflating the reported accuracy.

Failed refitting clears the old model. Training/calibration parcel overlap, future availability, wrong-region records, bad cents and missing essential training features are rejected. Artifact IDs bind the normalized source records, fitting/calibration boundary, seed, implementation hash and library versions. Known missing numeric values are imputed only from fitting data; malformed physical values are rejected, not silently converted to missing values.

Every report remains `research_only` or `needs_review`, with quote/offer authority and production readiness false. The reviewed comparable-sales engine is still the operator-approved evidence path. Sophia's existing consumer cannot treat this experimental method/status as a ready advisory valuation. The heavier libraries are an optional research extra, not default production dependencies. No model is deployed to a caller-facing price path.

## Accuracy-first improvements that also save time

1. Gather the most informative objective facts early: condition/quality, living and finished-basement area, permitted structure/style, construction/remodel history, lot and actual neighborhood. Missing these facts cannot be fixed by collecting many loosely similar sales.
2. Filter source availability, legal/property type and transaction context first. Preserve a verifiable source cache and reuse a model bound to a specific cutoff, region and code/data version; do not retrain or rescrape every seller utterance.
3. Batch inference after cheap scope checks. Keep preprocessing fitted and reused; avoid recalculating category encoding or missing-value statistics for each house. Use CPU threads with explicit limits and log-model comparison before considering more complex ensembles.
4. Inspect model-family disagreement and the historical residual band alongside source quality. Feature-importance percentages describe the fitted model, not causal value increments or approved dollar adjustments.
5. Keep raw historical research, current reviewed sales comparison, completed-scope ARV and investor purchase limits distinct. A house's renovation cost is not automatically its market-value gain.
6. Before automatic local pricing, collect current licensed California sold data, archive actual availability and condition evidence, then evaluate a newly sealed local cohort. Audit severe misses individually and calibrate segment-level uncertainty before granting price authority.

## Tests and reproduction

The optional research suite includes 1,000 individually parametrized source/feature/money invariance cases, plus actual three-family fitting/calibration, missing and unsupported input guards, cross-market denial, duplicate/temporal training rejection, failed-refit clearing and mixed valid/extreme batch handling. The full local suite passes 1,424 tests, retains the earlier 17,000 randomized comparison/finance/evidence scenarios, and passes 53 embedded-PostgreSQL migration/contracts. A separate CI job installs and exercises the optional estimators so default-production dependency isolation does not silently skip their verification.

```sh
uv sync --locked --extra valuation-research
uv run --extra valuation-research python scripts/benchmark_market_models.py /path/to/AmesHousing.txt --output /tmp/market-model-benchmark.json
uv run --extra valuation-research pytest -q
```

All monetary reports use bounded integer cents; floating-point arithmetic is confined to statistical fitting and log-price prediction. Fitting uses CPU only, no paid provider, no hosted training and no pickle loading. The harness downloads nothing and checks the supplied dataset's checksum.

## Remaining limits

This is a retrospective Iowa research benchmark. The dataset keeps only each parcel's latest sale and does not establish historical first-publication dates or as-of characteristic versions. A 30-day publication lag is an explicit assumption, not proof of historical availability. The 2010 set was examined previously, including exploratory comparisons in this pass; it is a repeated benchmark, not a newly sealed independent acceptance test. Target labels are excluded from fitting and calibration, but the data source's archival limitations prevent a fully leakage-free appraisal validation claim. Temporal drift, data-entry errors and sparse extreme-property examples still matter. Current Stockton/San Joaquin accuracy, renovation outcomes, independent source authenticity and real conversations remain unverified.
