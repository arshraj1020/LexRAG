package com.lexrag.api.dto.response;

import com.lexrag.domain.entities.Document;
import com.lexrag.domain.enums.DocumentStatus;

import java.time.Instant;
import java.util.UUID;

/**
 * Public-facing document representation. Storage path and owner ID are never exposed.
 */
public record DocumentResponse(
        UUID id,
        String title,
        String originalFilename,
        Long fileSizeBytes,
        DocumentStatus status,
        String errorMessage,

        // Extracted legal metadata (nullable)
        String caseName,
        String court,
        String jurisdiction,
        String caseNumber,
        String caseYear,
        String judges,
        String documentType,
        String language,
        Integer pageCount,
        Integer chunkCount,

        Instant createdAt,
        Instant updatedAt,
        Instant processedAt
) {
    public static DocumentResponse from(Document doc) {
        return new DocumentResponse(
                doc.getId(),
                doc.getTitle(),
                doc.getOriginalFilename(),
                doc.getFileSizeBytes(),
                doc.getStatus(),
                doc.getErrorMessage(),
                doc.getCaseName(),
                doc.getCourt(),
                doc.getJurisdiction(),
                doc.getCaseNumber(),
                doc.getCaseYear(),
                doc.getJudges(),
                doc.getDocumentType(),
                doc.getLanguage(),
                doc.getPageCount(),
                doc.getChunkCount(),
                doc.getCreatedAt(),
                doc.getUpdatedAt(),
                doc.getProcessedAt()
        );
    }
}
