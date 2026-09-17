package com.lexrag.api.dto.response;

import java.time.Instant;
import java.util.List;
import java.util.Map;

/**
 * Response from the precedent search pipeline.
 *
 * The precedents list is ranked by relevance (hybrid retrieval + cross-encoder reranking).
 * Each entry contains: rank, citation_id, case_name, court, year,
 * relevant_passage, page, paragraph, relevance_explanation, legal_principle.
 */
public record PrecedentSearchResponse(
        String query,
        /** Ranked precedent entries from the LLM. */
        List<Map<String, Object>> precedents,
        /** Citations verified against the database. */
        List<Map<String, Object>> verifiedCitations,
        /** Citations that failed verification. */
        List<Map<String, Object>> invalidCitations,
        int retrievedChunks,
        String confidence,
        Long latencyMs,
        Instant generatedAt,
        String disclaimer
) {
    public static final String LEGAL_DISCLAIMER =
            "Precedent search results are generated from retrieved document chunks by an AI assistant. "
            + "Rankings reflect retrieval relevance, not legal authority. "
            + "Always verify citations against primary sources. This is not legal advice.";
}
