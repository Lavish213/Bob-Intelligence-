# Bob randomized stress and recorded-sale grading — 2026-10-14

Bob's arithmetic and evidence checks pass this round. Automatic property pricing is not A-grade. Feature-based candidate selection improves the historical numerical diagnostic, but large real-sale errors remain. The safe production engine issues no advisory prices from this unreviewed dataset.

## What was tested

The original [Ames Housing text dataset](https://jse.amstat.org/v19n3/decock/AmesHousing.txt), documented by [Dean De Cock's primary-source paper](https://jse.amstat.org/v19n3/decock.pdf), contains 2,930 residential sales from Ames assessor records, 2006–2010. The source bytes have SHA-256 `6cfe6cb525ba437de428653a1040e2aed7d696640bf75203786a6d7a0e67cfcc`. Recorded sale price is a transaction outcome, not an official current market value or an ARV appraisal. Leading zeroes in parcel IDs are preserved.

A prespecified filter retains 1,943 normal warranty-deed detached-house sales; 505 other building types and 482 other transaction types are excluded. No ordinary sale is removed because its price looks inconvenient. Year 2009 provides a development diagnostic; the same selection rules were frozen before evaluating 2010. Results are an offline retrospective diagnostic: the source lacks archived publication timestamps, full transaction terms, source review and historical inspection evidence. It also retains only the latest sale per parcel. These gaps prevent a claim of fully leakage-free historical appraisal backtesting.

Targets are evaluated at the first day of their sale month. Candidate sales are assigned the last day of their recorded month and an assumed 30-day publication lag. Subject sales, same-month and later sales are excluded from candidate pools. The target's price does not enter ranking or estimation; it is revealed only for scoring. Both methods use identical eligible subjects and the same comp count. Twenty reproducible seeds randomize comps within the same neighborhood and preceding 365 days. Subject metadata is from the retrospective source; its historical availability is not independently established.

The strict production engine receives no fabricated verification, comparison review, contract dates, time/concession adjustment evidence or geographic distances. It therefore withholds all prices. A separate numeric diagnostic uses the engine's actual reconciliation core on unadjusted recorded sale prices with distance omitted. That diagnostic is deliberately not a sale-comparison appraisal or a test of reviewed adjusted ARV accuracy.

## 2010 result, after fixing equal comp counts

| Measure | Random same-neighborhood comps | Feature-ranked candidates |
|---|---:|---:|
| Eligible target houses | 215 | 215 |
| Estimates scored | 4,300 across 20 seeds | 215 |
| Mean absolute dollar error | $33,602.93 | $22,881.36 |
| Median absolute percentage error | 13.6788% | 9.8563% |
| Mean absolute percentage error | 19.3427% | 13.2455% |
| Mean signed percentage error | +3.1048% | +0.3703% |
| Within 10% of recorded sale | 1,691 / 4,300 | 110 / 215 |
| Worst absolute percentage error | 209.1293% | 131.5722% |
| Recorded sale inside observed comp-price span | 2,930 / 4,300 | 133 / 215 |

The mean dollar error improves about 31.9%; it still averages almost $23,000. Of 226 filtered 2010 targets, 11 lack at least three eligible ranked candidates and are not priced in the diagnostic. These shortfalls remain visible; they do not count as successful predictions. Neither span is a calibrated confidence interval. Random repeats are dependent observations of the same houses, not 4,300 independent property validations. No statistical significance or calibrated uncertainty claim is made.

The project error rubric is A ≤5%, B ≤10%, C ≤15%, D ≤20%, F >20% absolute error. It is an internal grading policy, not an industry standard. Feature-ranked 2010 cases: A=62, B=48, C=37, D=20, F=48. Its mean error corresponds to C on that rubric, and 48/215 houses miss by more than 20%. This is not sufficient for autonomous price quoting. As one failure, parcel `0531477050` sold for $67,500 while the unadjusted diagnostic returned $156,311.21. The report keeps that failure rather than hiding it. Condition details, effective age, basement finish, layout, objective location effects, terms and supported adjustments require source investigation; their causal contribution cannot be proved from these aggregate errors.

Year 2009 has 434 eligible targets and 8,680 random estimates. Feature-ranked median absolute percentage error is 8.5796%, versus 14.3747% for random comps. All per-seed metrics, exclusions, worst examples and assumptions are in `VALUATION-BENCHMARK-20261014.json`.

## Improvements shipped

- Exact Fraction reconciliation replaces intermediate Decimal weights in the point calculation. A reproduced half-cent case previously rounded $415,690.745 down by a cent; it now consistently rounds to $415,690.75 in every comp order. Display-only weights retain their existing decimal-string format.
- The flip purchase solver now uses rounded selling costs and verifies both feasibility at the returned amount and infeasibility one cent higher. Before the fix, 3,441 of 10,000 seeded scenarios understated a feasible limit by a cent. Conservative withholding for impossible profit targets remains.
- `rank_candidates` provides a price-blind review shortlist. It filters subject/duplicate records, nonclosed and known nonmarket sales, wrong property type/market, unavailable/stale records and living-area gaps above 25%. This is a configurable future research concern, not an appraisal rule. Its current 365-day/25% defaults are fixed software screening policies.
- Ranking uses normalized area/lot gaps, known feature differences and age. Its weights are transparent engineering heuristics, not local dollar adjustments or an accuracy guarantee. It does not create review attestations, fill missing facts, calculate a price or grant quote/offer authority. It helps an operator inspect better candidates faster.
- Offline usage: `python -m backend.valuation candidates.json --rank-candidates`. Input uses the existing subject/comparables/as_of shape. Candidate records need IDs, source reference, known features, type, market and sale/availability dates. A shortlist still needs independent transaction verification and complete comparison/adjustment review before the normal valuation command can use it.

## Repeatable stress checks

Twenty fixed seeds run 5,000 randomized reconciliations against an independent rational arithmetic oracle, including comp-order invariance, range bounds, large/small monetary values and input immutability. Twenty seeds run 10,000 flip scenarios against integer cent-rounding profit checks, including infeasible zero-price targets. Another twenty seeds run 2,000 malformed/nonmarket/unverified evidence cases, checking that missing or invalid records cannot produce a three-sale price. A syntactically valid source label is not proof of source authenticity; those stress tests do not claim to verify real records.

The suite also covers candidate selection's price blindness, duplicates, dates, property types/markets, absent features, no pricing authority, CLI output and benchmark leakage/grade/checksum behavior. Python test counts and CI results belong in the PR so a later code change does not silently inherit this run's grade.

## Concrete accuracy-first workflow

1. Cache source records with parcel ID, exact source/version, transaction date and actual first-available timestamp. Reuse the immutable cache instead of repeatedly searching the same record; never replace unknown timestamps with assumed ones in live pricing.
2. Filter availability, transaction type and competitive market before expensive analysis. Use the shortlist for review, not to fabricate sufficient comps. Its deterministic order and price-blind scoring avoid selecting comparables because they happen to support a desired price.
3. Inspect condition, quality, permitted area, effective age, layout, basement/ADU details, legal use, HOA and transaction terms. Require supported marginal-area/condition/time/concession adjustments rather than a universal price-per-foot multiplier or repair-dollar deduction.
4. Keep as-is value, completed-scope ARV and investor purchase limit separate. Recompute holding/financing assumptions for a changed duration or loan structure. Use integer cents and exact final feasibility checks.
5. Withhold a point estimate when evidence is insufficient or conflicting. A narrow observed comp span does not establish narrow uncertainty. Do not loosen review limits just to generate more prices.
6. Before promoting automatic pricing, obtain a current licensed/local sold-data sample and an independent final test. Test exact property/date evidence, calibration, segment errors and catastrophic misses. ARV also needs independently documented renovation scope and completed-condition outcomes; this dataset cannot grade it.

## Reproduce

Download the primary-source text file to a local input path, verify the pinned checksum, then run:

```sh
python scripts/benchmark_valuation.py /path/to/AmesHousing.txt --output /tmp/valuation-benchmark.json
python -m pytest -q
```

The harness downloads nothing, requires no paid provider, changes no database, sends no seller messages and never loads its numeric diagnostics into Sophia's quote path. Current Stockton/San Joaquin accuracy, live-source coverage, production deployment and real conversation performance remain unverified.
