# Rehab cost sources — what exists, what is usable, what is a trap

Research pass, 2026-11-08. The costbook in `backend/rehab/costbook.py` is labelled
`uncalibrated_placeholder_assumptions_not_contractor_bids`. This records what was
surveyed to replace those placeholders, and why most of it does not fit.

Two findings below are negative. They are the useful part, because each would
otherwise cost weeks to discover.

---

## 1. DDC CWICR — impressive, and the wrong tool

[OpenConstructionEstimate-DDC-CWICR](https://github.com/datadrivenconstruction/OpenConstructionEstimate-DDC-CWICR)
and [OpenConstructionERP](https://github.com/datadrivenconstruction/OpenConstructionERP)
are the only serious open construction cost databases found: 55,719 work items,
27,672 resources, 85 fields, distributed as Parquet, CSV, Excel and a Qdrant
snapshot with precomputed embeddings.

**Do not use it for Bob**, for three independent reasons:

1. **Licence.** The data is **CC BY-NC 4.0** — non-commercial. San Joaquin House
   Buyers is a commercial acquirer. Using it to price deals needs the separate DDC
   commercial licence. The code is Apache-2.0; the data is not.
2. **Provenance.** The source systems are Russian GESN/FER/TER, Chinese,
   Indonesian, Vietnamese, Greek, Italian, Spanish, Turkish and Brazilian norms.
   Derived tracks keep the **source track's labour and machine-hour norms** and
   only reprice via **World Bank PPP**. A `ddc_usa_usd` track exists but the repo
   does not state its source. A Russian labour norm converted by purchasing-power
   parity is not a Stockton subcontractor rate, however many rows sit behind it.
3. **No calibration.** The repo states no accuracy metrics and no calibration
   testing, and notes its cost formula and figures are illustrative.

Worth watching, not worth adopting. The row count is the most persuasive thing
about it and the least relevant.

## 2. Building permit valuations — biased twice over

My own earlier instinct was that permit records, which carry a declared job
valuation and are published as open data, would calibrate the costbook cheaply.
They will not, and the reasons compound:

- **Applicants under-declare**, because fees scale with valuation. One permit
  advisory states the saving plainly: an $80,000 kitchen declared at $40,000 saves
  several hundred dollars in fees.
- **Jurisdictions overwrite low declarations** with a calculated figure, so some
  records are not declarations at all.
- **The substitute is the ICC table** (below), so a share of "declared" values are
  really ICC averages wearing a declaration's clothes.
- **Scope differs.** Valuation covers permanent materials and labour but excludes
  design fees, financing and the permit fee itself.

Permit data is still useful for *detecting that work happened* — which is a
distress and condition signal Bob does not yet read. It is not a cost source.

## 3. ICC Building Valuation Data — real, public, and not an estimating guide

The [ICC Building Valuation Data](https://www.iccsafe.org/building-safety-journal/bsj-technical/building-valuation-data/)
table is referenced by more than 3,000 US jurisdictions and is republished in full
by many of them, so it is freely readable. It is updated every six months, in
February and August.

**ICC says directly that it is not intended to be used as an estimating guide**,
because it reflects average costs, and that its purpose is permit fee calculation.
It is also a **new-construction** per-square-foot table by occupancy and
construction type. Renovation is not what it measures.

Useful as a sanity bound on a whole-house figure. Not a line-item source.

## 4. BLS Producer Price Index — the one directly actionable source

`WPUSI012011`, Producer Price Index by Commodity, Special Indexes: Construction
Materials. Public BLS data, republished by FRED, monthly.

This does not tell you what a roof costs in Stockton. It tells you how much
construction materials have moved since the costbook was priced, which is the
difference between a costbook that ages visibly and one that rots silently.

Wired in: `costbook.py` declares the series, the date it was priced and a
183-day staleness window matching the ICC refresh cadence. `estimate_rehab`
accepts a current index reading and reprices every band by the exact integer
ratio. Until someone records the index value the costbook was actually priced at,
it reports `costbook_was_never_tied_to_an_index_reading_so_it_cannot_be_repriced`
rather than pretending.

Note the limit honestly: a materials index does not track labour, and labour is
the larger share of a rehab. Repricing by it is better than letting the book
drift, and worse than a fresh local quote.

## 5. Condition from images — PHI-Net is the closest open dataset, for a different problem

[PEER Hub ImageNet (Φ-Net)](https://apps.peer.berkeley.edu/phi-net), Gao & Mosalam,
*Journal of Structural Engineering* 146(10), DOI
[10.55461/PHIN01152018](https://doi.org/10.55461/PHIN01152018), is an open
multi-attribute structural image dataset covering eight recognition tasks with
thousands of images each.

It is built for **vision-based structural health monitoring** — earthquake and
structural damage assessment. That maps onto exactly one of Bob's scope areas,
`structural`, and that is the one area a photograph is already forbidden from
pricing. It does not help scope a kitchen.

No open dataset of **residential interior condition from listing photographs with
renovation-scope labels** was found. The commercial work in this space is patented
rather than published: several patents describe CNN classification of roof and
property condition from aerial imagery, which indicates the method is viable and
the data is proprietary.

## What would actually calibrate the costbook

In order of value per unit of effort:

1. **Ten to twenty completed local rehabs with final costs by scope area.** This
   is the only thing that turns placeholders into figures. Everything else above
   is a substitute for it.
2. **Contractor bid sheets** from the subs actually used, which also fix the
   labour share the PPI cannot see.
3. **Record the PPI reading at pricing time** so the book can be repriced between
   recalibrations.

Nothing open-source short-cuts item 1.
