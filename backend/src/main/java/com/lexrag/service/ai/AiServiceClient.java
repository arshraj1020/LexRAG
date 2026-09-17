package com.lexrag.service.ai;

import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;

import java.time.Duration;
import java.util.Map;

/**
 * HTTP client for backend → FastAPI AI service communication.
 *
 * All AI service calls go through this class. Reactive (WebClient) but
 * results are blocked where needed so callers remain non-reactive.
 */
@Component
@Slf4j
public class AiServiceClient {

    private static final Duration INGEST_TIMEOUT = Duration.ofSeconds(10);   // Returns immediately (background)
    private static final Duration GENERATE_TIMEOUT = Duration.ofSeconds(300); // LLM can be slow

    private final WebClient webClient;

    public AiServiceClient(@Qualifier("aiServiceWebClient") WebClient webClient) {
        this.webClient = webClient;
    }

    /**
     * Trigger document ingestion (async — AI service processes in background).
     * Returns quickly; the AI service updates document status independently.
     */
    public void triggerIngestion(String documentId, String filePath) {
        log.info("Triggering ingestion for document {}", documentId);
        try {
            webClient.post()
                    .uri("/internal/ingest")
                    .bodyValue(Map.of(
                            "document_id", documentId,
                            "file_path", filePath
                    ))
                    .retrieve()
                    .bodyToMono(Map.class)
                    .timeout(INGEST_TIMEOUT)
                    .block();
        } catch (WebClientResponseException ex) {
            log.error("AI service returned {} for ingest trigger: {}", ex.getStatusCode(), ex.getResponseBodyAsString());
            throw new AiServiceException("Failed to trigger ingestion: " + ex.getMessage(), ex);
        } catch (Exception ex) {
            log.error("Failed to contact AI service for ingestion", ex);
            throw new AiServiceException("AI service unavailable: " + ex.getMessage(), ex);
        }
    }

    /**
     * Generate a research answer via the full RAG pipeline.
     *
     * @return raw Map from AI service (answer, citations, verified_citations, confidence, etc.)
     */
    @SuppressWarnings("unchecked")
    public Map<String, Object> generate(GenerateRequest request) {
        log.info("Sending generate request: strategy={}, court={}, yearFrom={}, yearTo={}",
                request.strategy(), request.court(), request.yearFrom(), request.yearTo());

        // Build request body — exclude null filters to keep payload minimal
        java.util.Map<String, Object> body = new java.util.HashMap<>();
        body.put("question", request.question());
        body.put("document_ids", request.documentIds() != null ? request.documentIds() : java.util.List.of());
        body.put("strategy", request.strategy());
        if (request.court() != null && !request.court().isBlank()) {
            body.put("court", request.court());
        }
        if (request.yearFrom() != null) {
            body.put("year_from", request.yearFrom());
        }
        if (request.yearTo() != null) {
            body.put("year_to", request.yearTo());
        }

        try {
            return webClient.post()
                    .uri("/internal/generate")
                    .bodyValue(body)
                    .retrieve()
                    .bodyToMono(Map.class)
                    .timeout(GENERATE_TIMEOUT)
                    .block();
        } catch (WebClientResponseException ex) {
            log.error("AI service returned {} for generate: {}", ex.getStatusCode(), ex.getResponseBodyAsString());
            throw new AiServiceException("AI service error: " + ex.getMessage(), ex);
        } catch (Exception ex) {
            log.error("Failed to contact AI service for generate", ex);
            throw new AiServiceException("AI service unavailable: " + ex.getMessage(), ex);
        }
    }

    /** Typed request for generate — includes optional metadata filters. */
    public record GenerateRequest(
            String question,
            java.util.List<String> documentIds,
            String strategy,
            String court,
            Integer yearFrom,
            Integer yearTo
    ) {
        /** Convenience constructor without filters (for backward compat). */
        public GenerateRequest(String question, java.util.List<String> documentIds, String strategy) {
            this(question, documentIds, strategy, null, null, null);
        }
    }

    // ── Phase 3: Case Comparison ──────────────────────────────────────────────

    /**
     * Compare two or more legal cases via the AI service.
     * Returns structured JSON: facts, issues, arguments, similarities, differences, conflicts.
     */
    @SuppressWarnings("unchecked")
    public Map<String, Object> compare(CompareRequest request) {
        log.info("Sending compare request: question='{}', docs={}",
                request.question(), request.documentIds());

        java.util.Map<String, Object> body = new java.util.HashMap<>();
        body.put("question", request.question());
        body.put("document_ids", request.documentIds());
        if (request.court() != null && !request.court().isBlank()) {
            body.put("court", request.court());
        }
        if (request.yearFrom() != null) body.put("year_from", request.yearFrom());
        if (request.yearTo() != null)   body.put("year_to", request.yearTo());

        try {
            return webClient.post()
                    .uri("/internal/compare")
                    .bodyValue(body)
                    .retrieve()
                    .bodyToMono(Map.class)
                    .timeout(GENERATE_TIMEOUT)
                    .block();
        } catch (WebClientResponseException ex) {
            log.error("AI service returned {} for compare: {}", ex.getStatusCode(), ex.getResponseBodyAsString());
            throw new AiServiceException("AI service error (compare): " + ex.getMessage(), ex);
        } catch (Exception ex) {
            log.error("Failed to contact AI service for compare", ex);
            throw new AiServiceException("AI service unavailable: " + ex.getMessage(), ex);
        }
    }

    // ── Phase 3: Precedent Search ─────────────────────────────────────────────

    /**
     * Search for relevant precedents using hybrid retrieval + reranking.
     */
    @SuppressWarnings("unchecked")
    public Map<String, Object> findPrecedents(PrecedentRequest request) {
        log.info("Sending precedent request: query='{}', court={}, yearFrom={}",
                request.query(), request.court(), request.yearFrom());

        java.util.Map<String, Object> body = new java.util.HashMap<>();
        body.put("query", request.query());
        if (request.documentIds() != null) body.put("document_ids", request.documentIds());
        if (request.court() != null && !request.court().isBlank()) body.put("court", request.court());
        if (request.jurisdiction() != null && !request.jurisdiction().isBlank())
            body.put("jurisdiction", request.jurisdiction());
        if (request.yearFrom() != null)  body.put("year_from", request.yearFrom());
        if (request.yearTo() != null)    body.put("year_to", request.yearTo());
        if (request.topK() != null)      body.put("top_k", request.topK());

        try {
            return webClient.post()
                    .uri("/internal/precedents")
                    .bodyValue(body)
                    .retrieve()
                    .bodyToMono(Map.class)
                    .timeout(GENERATE_TIMEOUT)
                    .block();
        } catch (WebClientResponseException ex) {
            log.error("AI service returned {} for precedents: {}", ex.getStatusCode(), ex.getResponseBodyAsString());
            throw new AiServiceException("AI service error (precedents): " + ex.getMessage(), ex);
        } catch (Exception ex) {
            log.error("Failed to contact AI service for precedents", ex);
            throw new AiServiceException("AI service unavailable: " + ex.getMessage(), ex);
        }
    }

    // ── Phase 3: Legal Provision Analysis ─────────────────────────────────────

    /**
     * Analyse how courts have interpreted a statutory provision.
     */
    @SuppressWarnings("unchecked")
    public Map<String, Object> analyseProvision(ProvisionRequest request) {
        log.info("Sending provision request: provision='{}'", request.provision());

        java.util.Map<String, Object> body = new java.util.HashMap<>();
        body.put("provision", request.provision());
        if (request.documentIds() != null) body.put("document_ids", request.documentIds());
        if (request.court() != null && !request.court().isBlank()) body.put("court", request.court());
        if (request.yearFrom() != null)  body.put("year_from", request.yearFrom());
        if (request.yearTo() != null)    body.put("year_to", request.yearTo());

        try {
            return webClient.post()
                    .uri("/internal/provision")
                    .bodyValue(body)
                    .retrieve()
                    .bodyToMono(Map.class)
                    .timeout(GENERATE_TIMEOUT)
                    .block();
        } catch (WebClientResponseException ex) {
            log.error("AI service returned {} for provision: {}", ex.getStatusCode(), ex.getResponseBodyAsString());
            throw new AiServiceException("AI service error (provision): " + ex.getMessage(), ex);
        } catch (Exception ex) {
            log.error("Failed to contact AI service for provision", ex);
            throw new AiServiceException("AI service unavailable: " + ex.getMessage(), ex);
        }
    }

    // ── Phase 3: Research Brief ────────────────────────────────────────────────

    /**
     * Generate a structured legal research brief from the user's document corpus.
     */
    @SuppressWarnings("unchecked")
    public Map<String, Object> generateBrief(BriefRequest request) {
        log.info("Sending brief request: question='{}', docs={}",
                request.researchQuestion(), request.documentIds());

        java.util.Map<String, Object> body = new java.util.HashMap<>();
        body.put("research_question", request.researchQuestion());
        if (request.documentIds() != null) body.put("document_ids", request.documentIds());
        if (request.court() != null && !request.court().isBlank()) body.put("court", request.court());
        if (request.jurisdiction() != null && !request.jurisdiction().isBlank())
            body.put("jurisdiction", request.jurisdiction());
        if (request.yearFrom() != null) body.put("year_from", request.yearFrom());
        if (request.yearTo() != null)   body.put("year_to", request.yearTo());
        if (request.documentType() != null && !request.documentType().isBlank())
            body.put("document_type", request.documentType());

        try {
            return webClient.post()
                    .uri("/internal/brief")
                    .bodyValue(body)
                    .retrieve()
                    .bodyToMono(Map.class)
                    .timeout(GENERATE_TIMEOUT)
                    .block();
        } catch (WebClientResponseException ex) {
            log.error("AI service returned {} for brief: {}", ex.getStatusCode(), ex.getResponseBodyAsString());
            throw new AiServiceException("AI service error (brief): " + ex.getMessage(), ex);
        } catch (Exception ex) {
            log.error("Failed to contact AI service for brief", ex);
            throw new AiServiceException("AI service unavailable: " + ex.getMessage(), ex);
        }
    }

    // ── Phase 3 request records ────────────────────────────────────────────────

    /** Request for multi-document case comparison. */
    public record CompareRequest(
            String question,
            java.util.List<String> documentIds,
            String court,
            Integer yearFrom,
            Integer yearTo
    ) {}

    /** Request for precedent search with metadata filters. */
    public record PrecedentRequest(
            String query,
            java.util.List<String> documentIds,
            String court,
            String jurisdiction,
            Integer yearFrom,
            Integer yearTo,
            Integer topK
    ) {}

    /** Request for statutory provision analysis. */
    public record ProvisionRequest(
            String provision,
            java.util.List<String> documentIds,
            String court,
            Integer yearFrom,
            Integer yearTo
    ) {}

    /** Request for a full structured research brief. */
    public record BriefRequest(
            String researchQuestion,
            java.util.List<String> documentIds,
            String court,
            String jurisdiction,
            Integer yearFrom,
            Integer yearTo,
            String documentType
    ) {}

    /** Runtime exception for AI service communication failures. */
    public static class AiServiceException extends RuntimeException {
        public AiServiceException(String message, Throwable cause) {
            super(message, cause);
        }
    }
}
