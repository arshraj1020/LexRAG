package com.lexrag.api.dto.request;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

import java.util.List;
import java.util.UUID;

/**
 * Request for precedent search with hybrid retrieval and metadata filters.
 */
public record PrecedentSearchRequest(

        @NotBlank(message = "Query must not be blank")
        @Size(min = 5, max = 2000, message = "Query must be between 5 and 2000 characters")
        String query,

        /** Optional: restrict search to specific documents. Null = all user's documents. */
        List<UUID> documentIds,

        /** Optional metadata filters. */
        String court,
        String jurisdiction,
        Integer yearFrom,
        Integer yearTo,

        /** Number of precedents to return. Defaults to 10 if null. */
        @Min(1) @Max(25)
        Integer topK
) {
    public int effectiveTopK() {
        return topK != null ? topK : 10;
    }
}
