package com.lexrag.service.impl;

import com.lexrag.domain.enums.DocumentStatus;
import com.lexrag.domain.repositories.DocumentRepository;
import com.lexrag.service.ai.AiServiceClient;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.util.UUID;

/**
 * Handles async document ingestion coordination.
 *
 * This is a separate @Component so that the @Async proxy works correctly.
 * Spring @Async requires the method to be called through a Spring proxy,
 * which does not happen for self-calls (this.method()). Extracting to a
 * separate bean ensures the proxy wraps the async method.
 */
@Component
@RequiredArgsConstructor
@Slf4j
public class IngestionCoordinator {

    private final AiServiceClient aiServiceClient;
    private final DocumentRepository documentRepository;

    /**
     * Mark as PROCESSING, call AI service to start ingestion, and handle errors.
     * Runs in a thread pool thread — never blocks the HTTP request thread.
     *
     * <p>NOTE: This method is NOT @Transactional. Each status-update helper
     * opens its own short transaction (REQUIRES_NEW), so no DB connection is
     * held open during the potentially-slow HTTP call to the AI service.
     */
    @Async
    public void triggerAsync(String documentId, String filePath) {
        UUID docUuid = UUID.fromString(documentId);

        markProcessing(docUuid);

        try {
            aiServiceClient.triggerIngestion(documentId, filePath);
            log.info("Ingestion triggered successfully for document {}", documentId);
        } catch (AiServiceClient.AiServiceException ex) {
            log.error("Ingestion trigger failed for document {}", documentId, ex);
            markFailed(docUuid, "Failed to start ingestion: " + ex.getMessage());
        }
    }

    /** Open a short transaction to mark the document PROCESSING. */
    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void markProcessing(UUID docId) {
        documentRepository.findById(docId).ifPresent(doc -> {
            doc.setStatus(DocumentStatus.PROCESSING);
            doc.setUpdatedAt(Instant.now());
            documentRepository.save(doc);
        });
    }

    /** Open a short transaction to mark the document FAILED. */
    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void markFailed(UUID docId, String errorMessage) {
        documentRepository.findById(docId).ifPresent(doc -> {
            doc.setStatus(DocumentStatus.FAILED);
            doc.setErrorMessage(errorMessage);
            doc.setUpdatedAt(Instant.now());
            documentRepository.save(doc);
        });
    }
}
