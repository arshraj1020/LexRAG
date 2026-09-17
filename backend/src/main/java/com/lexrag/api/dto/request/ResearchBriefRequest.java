package com.lexrag.api.dto.request;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

import java.util.List;
import java.util.UUID;

/**
 * Request to generate a full structured legal research brief.
 *
 * The brief covers: executive summary, key findings, relevant authorities,
 * arguments, supporting/conflicting evidence, open questions, and conclusion.
 * All sections are grounded in citations from retrieved evidence.
 */
public record ResearchBriefRequest(

        @NotBlank(message = "Research question must not be blank")
        @Size(min = 10, max = 2000, message = "Research question must be between 10 and 2000 characters")
        String researchQuestion,

        /** Optional: restrict search to specific documents. Null = all user's documents. */
        List<UUID> documentIds,

        /** Optional metadata filters. */
        String court,
        String jurisdiction,
        Integer yearFrom,
        Integer yearTo,

        /**
         * Optional document type filter (e.g. "judgment", "order", "opinion").
         * Passed to the retrieval pipeline to narrow the corpus.
         */
        String documentType
) {}
