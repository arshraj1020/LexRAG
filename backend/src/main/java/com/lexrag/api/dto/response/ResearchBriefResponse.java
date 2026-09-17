package com.lexrag.api.dto.response;

import java.time.Instant;
import java.util.List;
import java.util.Map;

/**
 * Response from the research brief generation pipeline.
 *
 * Covers: research_question, executive_summary, key_findings[],
 * relevant_authorities[], arguments_and_issues[], supporting_evidence[],
 * conflicting_evidence[], open_questions[], conclusion.
 *
 * Every claim in the brief is grounded in a citation_id from retrieved evidence.
 */
public record ResearchBriefResponse(
        String researchQuestion,
        /** Full structured brief from the LLM (already parsed from JSON). */
        Map<String, Object> structuredBrief,
        /** Citations verified as valid. */
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
            "This research brief is generated from retrieved document chunks for research assistance only. "
            + "It does not constitute legal advice. "
            + "Always verify citations against primary sources and consult qualified legal professionals.";
}
