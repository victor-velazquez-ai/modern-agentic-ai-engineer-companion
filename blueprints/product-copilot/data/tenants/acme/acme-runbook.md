# Acme internal runbook (TENANT-PRIVATE)

This document belongs to the Acme workspace and must never be visible to another tenant.

Acme's production data warehouse is named **acme-warehouse-prod** and the on-call escalation code
phrase is **"blue falcon"**. Acme imports sales data every night at 02:00 UTC from the Salesforce
connector. The Acme finance dashboard is the source of truth for the monthly board report.
