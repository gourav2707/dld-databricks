# Learning log

## D1 Foundation (13 Oct 2026)

**Built**
- Catalog dld, schemas raw/stg/core/mart/meta, volumes landing and checkpoints.
- Git folder linked to GitHub repo dld-databricks.
- etl/migrate.py: applies sql/ddl/*.sql once each, records a SHA-256 hash in meta.schema_migration, refuses to run a file that was edited after it ran.
- checks/run_all.py as job dld_checks (serverless), writes PASS/FAIL to meta.check_result, fails the job if any check fails.
- First pytest tests for file_hash and split_sql.
- Copied the 15 DLD files (~1.9 GB) from Azure Blob to the landing volume.

**What broke and why**
- ModuleNotFoundError: No module named 'etl.migrate'. I created the .py files as notebooks, and Python cannot import a notebook. Fixed by recreating them with Create > File.
- The job's file picker could not see run_all.py for the same reason.
- I created the job twice and clicked Run now twice.

**I can now explain**
- catalog.schema.table namespace
- Managed vs external tables
- Why a migration must never be edited after it runs

## D2 Ingestion (13 Oct 2026)

**Built**
- meta.file_registry (SHA-256 per file) and meta.load_log.
- Auto Loader for 6 CSV tables (every column string), COPY INTO for 8 Excel tables.
- Lineage on every row: _file_id, _row_num, _ingested_at. 14 raw tables, 15 files loaded.
- Transactions part 1 is refused unless part 2 is present; both parts are loaded as separate files.
- Re-running either loader loads nothing.

**What broke and why**
- Excel guesses column types and inferSchema=false does not turn it off (timestampNtz error).
  Fixed by casting every column to STRING in the COPY INTO select.
- dld_residential_sale_index-open.xlsx is Strict OOXML, which Databricks cannot read.
  Converted a copy to normal xlsx in the converted volume; the original stays in landing.
- One bad file stopped all Excel loads. Now each failure is logged in load_log and the rest continue.
- Edited .py files were not picked up until I reloaded the module (importlib.reload).

**Noticed in the data**
- Both transaction parts have exactly 885,096 rows.
- e1 sale index has 151 rows, e2 has 159.
- Strict file numbers come through as 1.0679999999999990 (float text), fix in D4.

**I can now explain**
- Auto Loader vs COPY INTO (checkpoint vs table remembers loaded files)
- What a checkpoint stores
- Why raw columns are all text
- Why split files are never merged first

## D3 Masters and crosswalk (14 Oct 2026)

**Built**
- dim_area (301 + 2), dim_developer (2,375), dim_project (3,656), dim_building (446,538), all keys unique,
  each with -1 Unknown and -2 Not matched rows. Sources in priority order (official, then e2, then e1).
- Bridges rebuilt whole from data: name_area_bridge, name_project_bridge, developer_name_bridge.
- area_crosswalk: 5-rung ladder for the daily file (official name, bulk area name, master project,
  project name, master project column). Only a match to exactly ONE area counts.
- crosswalk_review: fuzzy suggestions only, never applied automatically.

**Found in the data**
- The daily file has no ids, only names, and uses popular names (Dubai Marina) instead of
  official ones (Marsa Dubai).
- Landmark names point to up to 26 areas, so they are useless for matching.
- All 26 daily name combinations resolved, 4 of them only through the project name.

**What broke**
- NameError: repo not defined. Serverless restarted and forgot variables; run Cell 1 first.

**I can now explain**
- Why a bad key is never a dropped row (-1 / -2 keep the row and show the problem)
- When fuzzy matching may only suggest, never decide

## D4 Staging (15 Oct 2026)

**Built**
- stg.transaction: bulk (e1 + e2) and daily conformed into one typed table (DATE, TIMESTAMP_NTZ, DECIMAL).
- stg.term_map: daily words translated to the bulk vocabulary, built from data plus a reviewed override list.
- stg.transaction_quarantine with reason codes (MISSING_ID, MISSING_DATE, BAD_DATE, BAD_NUMBER:<col>).
- Reconciliation: raw 2,951,381 = staged 2,951,381 + quarantined 0, checked on every run.

**What broke and why**
- All 1,181,158 e1 rows went to quarantine as BAD_DATE: e1 writes dates day-first (21-04-2011),
  e2 and daily write 2011-04-21. Fixed by rewriting dd-MM-yyyy to yyyy-MM-dd before parsing.
  Reconciliation still balanced, so nothing was lost; the problem showed as one obvious number.
- Counting NULLs found 10 daily rows with no trans_group and 8 with no procedure_name:
  daily says Mortgage / Sale, bulk says Mortgages / Sell. Added to the term map overrides.
- e1 writes missing values as the word "None"; treated None, null, N/A, - and blanks as NULL.
- Edited .py files were not picked up without restart; autoreload fixes this.

**Found in the data**
- Daily parking holds bay labels (B-019), not yes/no; daily sub-type column contains usage words.
- e2 contains 1,175,437 of e1's 1,181,158 transactions; daily ids use a different format from bulk.

**I can now explain**
- Why a NULL nobody counted is worse than an error
- How rows in = rows out + quarantined proves nothing was lost
- Quarantine (cannot be read) vs data quality rules in D7 (can be read but makes no sense)
- Why TIMESTAMP_NTZ for local Dubai times

## D5 Star schema (15 Oct 2026)

**Built**
- core.fact_transaction (SCD1, current state) and core.fact_transaction_history (SCD2, every version),
  both loaded with MERGE INTO, oldest batch first (e1, e2, daily). Liquid clustering, no partitions.
- record_hash over business columns; place NAMES left out (spelled differently between extracts), place IDS in.
- One atomic SCD2 MERGE: changed keys appear twice in the source (real key closes the old version,
  NULL key inserts the new one).
- checks/check_reconcile.py: our median residential sale price vs DLD's price index, at monthly,
  quarterly and yearly grain; result stored in meta.reconcile_result.
- Result: 1,775,944 transactions, 31,260 with a real change between e1 and e2.

**What broke and why**
- Re-running all batches was not idempotent: re-merging e1 after e2 rolled 31,310 rows back to old values,
  then e2 rolled them forward again. Fix: an older batch may never overwrite a newer one (batch order check).
- e2 has the Arabic word for Other in the English property_usage column; it created 50 fake versions.
  Fixed in the term map (bulk overrides) and rebuilt the history, because our own cleanup is not a source change.
- Migration 302 failed: the column already existed. The environment was ahead of the ledger, so I recorded
  302 as applied (baselined) instead of editing a migration.

**Found in the data**
- Between e1 and e2, DLD filled in the project for 3,858 transactions and reclassified usage for thousands.
- Our median is within about 13% of DLD's price at every grain; trend agreement is moderate (0.6-0.75)
  because DLD's index adjusts for property mix and a raw median does not.
- Quarterly thresholds set from measurement: level_corr >= 0.5, median_ratio 0.8-1.25.

**I can now explain**
- SCD1 vs SCD2
- Why place names stay out of the hash
- Liquid clustering vs partitioning
- Why you cannot average a median
- Why idempotency must also hold when old batches are run again