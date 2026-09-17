package com.lexrag.api.dto.request;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.Size;

import java.util.List;
import java.util.UUID;

/**
 * Request to compare two or more legal cases.
 * documentIds must contain at least two documents for a meaningful comparison.
 */
public record CaseComparisonRequest(

        @NotBlank(message = "Comparison question must not be blank")
        @Size(min = 10, max = 2000, message = "Question must be between 10 and 2000 characters")
        String question,

        /** At least 2 document IDs required for comparison. */
        @NotEmpty(message = "At least two document IDs are required for case comparison")
        @Size(min = 2, max = 10, message = "Provide between 2 and 10 documents for comparison")
        List<UUID> documentIds,

        /** Optional metadata filters. */
        String court,
        Integer yearFrom,
        Integer yearTo
) {}
