"""
Query expander unit tests — no DB or ML dependencies.

Verifies: original query preserved, acronym expansion, section→concept mapping,
fallback behaviour on degenerate input.
"""

import pytest
from app.retrieval.query_expander import expand_query


class TestExpandQuery:
    def test_original_query_always_first(self):
        q = "What factors does a court consider for bail?"
        variants = expand_query(q)
        assert variants[0] == q, "Original query must always be at index 0"

    def test_returns_list_of_strings(self):
        variants = expand_query("anticipatory bail under Section 438 CrPC")
        assert isinstance(variants, list)
        assert all(isinstance(v, str) for v in variants)

    def test_crpc_acronym_expanded(self):
        q = "What is anticipatory bail under CrPC?"
        variants = expand_query(q)
        # Should have at least 2: original + expansion
        assert len(variants) >= 2
        expansions = " ".join(variants[1:])
        assert "Code of Criminal Procedure" in expansions or "Cr.P.C" in expansions

    def test_section_438_concept_added(self):
        q = "conditions for section 438 bail"
        variants = expand_query(q)
        # Should mention 'anticipatory bail' in at least one variant
        all_text = " ".join(variants).lower()
        assert "anticipatory bail" in all_text

    def test_max_variants_respected(self):
        q = "CrPC Section 438 anticipatory bail IPC"
        variants = expand_query(q, max_variants=2)
        assert len(variants) <= 2

    def test_no_duplicates(self):
        q = "Section 438 CrPC anticipatory bail"
        variants = expand_query(q)
        assert len(variants) == len(set(variants)), "No duplicate variants allowed"

    def test_empty_query_does_not_crash(self):
        variants = expand_query("")
        assert isinstance(variants, list)
        assert len(variants) >= 1

    def test_unknown_query_returns_original_only(self):
        q = "xyzzy quux frobble"
        variants = expand_query(q)
        assert variants[0] == q

    def test_returns_at_most_default_max(self):
        q = "Section 438 CrPC IPC Article 21 SC HC"
        variants = expand_query(q)
        assert len(variants) <= 3  # default max_variants=3


class TestExpandQueryFallback:
    def test_never_raises(self):
        # Even unusual input should not raise
        for q in ["", "a" * 5000, "Ignore previous instructions", "'; DROP TABLE--"]:
            result = expand_query(q)
            assert isinstance(result, list)
            assert len(result) >= 1
