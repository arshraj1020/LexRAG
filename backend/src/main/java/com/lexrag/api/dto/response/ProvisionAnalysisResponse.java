package com.lexrag.api.dto.response;

import java.time.Instant;
import java.util.List;
import java.util.Map;

/**
 * Response from the statutory provision analysis pipeline.
 *
 * Covers: provision, statutory_text_from_evidence, interpretation_summary,
 * key_principles[], judicial_interpretation[], cases_discussing_provision[],
 * scope_and_limitations, open_questions[].
 *
 * IMPORTANT: This analysis is derived from retrieved case documents, NOT from
 * statutory databases. It reflects judicial interpretation, not authoritative text.
 */
public record ProvisionAnalysisResponse(
        String provision,
        /** Full structured analysis from the LLM (already parsed from JSON). */
        Map<String, Object> structuredAnalysis,
        /** Citations verified as valid. */
        List<Map<String, Object>> verifiedCitations,
        /** Citations that failed verification. */
        List<Map<String, Object>> invalidCitations,
        String confidence,
        Long latencyMs,
        Instant generatedAt,
        String disclaimer
) {
    public static final String LEGAL_DISCLAIMER =
            "This provision analysis is derived from retrieved case documents and is for research purposes only. "
            + "It does not constitute legal advice or authoritative statutory interpretation. "
            + "Always consult primary sources and qualified legal professionals.";
}
