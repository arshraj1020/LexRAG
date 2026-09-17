package com.lexrag.api.dto.request;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

import java.util.List;
import java.util.UUID;

/**
 * Request to analyse how courts have interpreted a statutory provision.
 * The provision field should identify the section/clause (e.g. "Section 34 CPC",
 * "Article 21 Constitution of India").
 */
public record ProvisionAnalysisRequest(

        @NotBlank(message = "Provision must not be blank")
        @Size(min = 3, max = 500, message = "Provision must be between 3 and 500 characters")
        String provision,

        /** Optional: restrict search to specific documents. Null = all user's documents. */
        List<UUID> documentIds,

        /** Optional metadata filters. */
        String court,
        Integer yearFrom,
        Integer yearTo
) {}
