package com.lexrag.api.dto.request;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

import java.util.List;
import java.util.UUID;

public record ResearchQueryRequest(

        @NotBlank(message = "Question must not be blank")
        @Size(min = 10, max = 2000, message = "Question must be between 10 and 2000 characters")
        String question,

        /** Optional: restrict search to specific documents. Null = all user's documents. */
        List<UUID> documentIds,

        /**
         * Retrieval strategy:
         * DENSE        — vector similarity only (fastest, least accurate)
         * HYBRID       — dense + keyword FTS with RRF fusion
         * HYBRID_RERANK — hybrid + cross-encoder reranking (slowest, most accurate)
         */
        @Pattern(regexp = "^(DENSE|HYBRID|HYBRID_RERANK)$",
                 message = "Strategy must be DENSE, HYBRID, or HYBRID_RERANK")
        String strategy,

        /** Optional metadata filters */
        String court,
        Integer yearFrom,
        Integer yearTo
) {
    public String effectiveStrategy() {
        return strategy != null ? strategy : "HYBRID_RERANK";
    }
}
