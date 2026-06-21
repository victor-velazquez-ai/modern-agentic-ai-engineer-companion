"""Permissioned ingestion for the Internal Knowledge Assistant.

``sync_acl`` loads the corpus, stamps each document's ACL groups onto its metadata, then chunks,
embeds, and indexes it (composing the rag-pipeline pattern blueprint). The ACL stamp is what the
query-path *filter-before-retrieval* rule in ``app.kb_assistant`` relies on.
"""
