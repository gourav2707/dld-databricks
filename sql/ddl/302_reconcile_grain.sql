-- D5: reconciliation is now measured at monthly, quarterly and yearly grain
ALTER TABLE dld.meta.reconcile_result ADD COLUMNS (grain STRING);