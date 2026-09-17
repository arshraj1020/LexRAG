package com.lexrag.service.impl;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.lexrag.api.dto.request.CaseComparisonRequest;
import com.lexrag.api.dto.request.PrecedentSearchRequest;
import com.lexrag.api.dto.request.ProvisionAnalysisRequest;
import com.lexrag.api.dto.request.ResearchBriefRequest;
import com.lexrag.api.dto.request.ResearchQueryRequest;
import com.lexrag.api.dto.response.CaseComparisonResponse;
import com.lexrag.api.dto.response.PageResponse;
import com.lexrag.api.dto.response.PrecedentSearchResponse;
import com.lexrag.api.dto.response.ProvisionAnalysisResponse;
import com.lexrag.api.dto.response.ResearchBriefResponse;
import com.lexrag.api.dto.response.ResearchQueryResponse;
import com.lexrag.domain.entities.Document;
import com.lexrag.domain.entities.ResearchQuery;
import com.lexrag.domain.entities.ResearchSession;
import com.lexrag.domain.entities.User;
import com.lexrag.domain.repositories.DocumentRepository;
import com.lexrag.domain.repositories.ResearchSessionRepository;
import com.lexrag.exception.ResourceNotFoundException;
import com.lexrag.service.ai.AiServiceClient;
import com.lexrag.service.interfaces.ResearchService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@Service
@RequiredArgsConstructor
@Slf4j
public class ResearchServiceImpl implements ResearchService {

    private final AiServiceClient aiServiceClient;
    private final ResearchSessionRepository sessionRepository;
    private final DocumentRepository documentRepository;
    private final ObjectMapper objectMapper;

    @Override
    @Transactional
    public ResearchQueryResponse query(ResearchQueryRequest request, User user) {
        long startMs = System.currentTimeMillis();

        // Convert UUID list to String list for AI service
        List<String> documentIdStrings = request.documentIds() != null
                ? request.documentIds().stream().map(UUID::toString).toList()
                : null;

        String strategy = request.effectiveStrategy();

        // Call AI service — pass metadata filters so the retrieval can be scoped
        Map<String, Object> aiResponse = aiServiceClient.generate(
                new AiServiceClient.GenerateRequest(
                        request.question(),
                        documentIdStrings,
                        strategy,
                        request.court(),
                        request.yearFrom(),
                        request.yearTo()
                )
        );

        long latencyMs = System.currentTimeMillis() - startMs;

        String answer = (String) aiResponse.getOrDefault("answer", "");
        @SuppressWarnings("unchecked")
        List<Map<String, Object>> verifiedCitations =
                (List<Map<String, Object>>) aiResponse.getOrDefault("verified_citations", List.of());
        Double confidence = aiResponse.get("confidence") instanceof Number n
                ? n.doubleValue() : null;
        Integer retrievedChunks = aiResponse.get("retrieved_chunks") instanceof Number n
                ? n.intValue() : null;

        // Persist the query to a default session for this user
        ResearchSession session = getOrCreateDefaultSession(user);
        ResearchQuery savedQuery = persistQuery(
                session, request.question(), answer,
                aiResponse, verifiedCitations, latencyMs, strategy
        );

        return new ResearchQueryResponse(
                savedQuery.getId(),
                request.question(),
                answer,
                verifiedCitations,
                strategy,
                confidence,
                retrievedChunks,
                latencyMs,
                savedQuery.getCreatedAt(),
                ResearchQueryResponse.LEGAL_DISCLAIMER
        );
    }

    @Override
    @Transactional(readOnly = true)
    public PageResponse<ResearchSessionSummary> listSessions(UUID userId, int page, int size) {
        Page<ResearchSession> sessions = sessionRepository.findByUserIdOrderByCreatedAtDesc(
                userId, PageRequest.of(page, size));
        return PageResponse.from(sessions, this::toSessionSummary);
    }

    @Override
    @Transactional(readOnly = true)
    public ResearchSessionDetail getSession(UUID sessionId, UUID userId) {
        ResearchSession session = sessionRepository.findByIdAndUserId(sessionId, userId)
                .orElseThrow(() -> new ResourceNotFoundException("Session not found: " + sessionId));
        return toSessionDetail(session);
    }

    // ── Phase 3: Case Comparison ──────────────────────────────────────────────

    @Override
    @Transactional(readOnly = true)
    public CaseComparisonResponse compare(CaseComparisonRequest request, User user) {
        long startMs = System.currentTimeMillis();

        // Enforce owner isolation — all documentIds must belong to this user
        List<String> ownedDocIds = resolveOwnedDocIds(request.documentIds(), user.getId());
        if (ownedDocIds.size() < 2) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                    "At least 2 documents owned by you are required for comparison. "
                    + "Check that the provided document IDs belong to your account.");
        }

        Map<String, Object> aiResponse = aiServiceClient.compare(
                new AiServiceClient.CompareRequest(
                        request.question(), ownedDocIds,
                        request.court(), request.yearFrom(), request.yearTo()
                )
        );

        long latencyMs = System.currentTimeMillis() - startMs;
        return buildComparisonResponse(request.question(), aiResponse, latencyMs);
    }

    // ── Phase 3: Precedent Search ─────────────────────────────────────────────

    @Override
    @Transactional(readOnly = true)
    public PrecedentSearchResponse findPrecedents(PrecedentSearchRequest request, User user) {
        long startMs = System.currentTimeMillis();

        List<String> docIds = request.documentIds() != null
                ? resolveOwnedDocIds(request.documentIds(), user.getId())
                : allOwnedDocIds(user.getId());

        Map<String, Object> aiResponse = aiServiceClient.findPrecedents(
                new AiServiceClient.PrecedentRequest(
                        request.query(), docIds,
                        request.court(), request.jurisdiction(),
                        request.yearFrom(), request.yearTo(),
                        request.effectiveTopK()
                )
        );

        long latencyMs = System.currentTimeMillis() - startMs;
        return buildPrecedentResponse(request.query(), aiResponse, latencyMs);
    }

    // ── Phase 3: Provision Analysis ───────────────────────────────────────────

    @Override
    @Transactional(readOnly = true)
    public ProvisionAnalysisResponse analyseProvision(ProvisionAnalysisRequest request, User user) {
        long startMs = System.currentTimeMillis();

        List<String> docIds = request.documentIds() != null
                ? resolveOwnedDocIds(request.documentIds(), user.getId())
                : allOwnedDocIds(user.getId());

        Map<String, Object> aiResponse = aiServiceClient.analyseProvision(
                new AiServiceClient.ProvisionRequest(
                        request.provision(), docIds,
                        request.court(), request.yearFrom(), request.yearTo()
                )
        );

        long latencyMs = System.currentTimeMillis() - startMs;
        return buildProvisionResponse(request.provision(), aiResponse, latencyMs);
    }

    // ── Phase 3: Research Brief ────────────────────────────────────────────────

    @Override
    @Transactional(readOnly = true)
    public ResearchBriefResponse generateBrief(ResearchBriefRequest request, User user) {
        long startMs = System.currentTimeMillis();

        List<String> docIds = request.documentIds() != null
                ? resolveOwnedDocIds(request.documentIds(), user.getId())
                : allOwnedDocIds(user.getId());

        Map<String, Object> aiResponse = aiServiceClient.generateBrief(
                new AiServiceClient.BriefRequest(
                        request.researchQuestion(), docIds,
                        request.court(), request.jurisdiction(),
                        request.yearFrom(), request.yearTo(),
                        request.documentType()
                )
        );

        long latencyMs = System.currentTimeMillis() - startMs;
        return buildBriefResponse(request.researchQuestion(), aiResponse, latencyMs);
    }

    // ── Private helpers ───────────────────────────────────────

    private ResearchSession getOrCreateDefaultSession(User user) {
        return sessionRepository.findByUserIdOrderByCreatedAtDesc(
                        user.getId(), PageRequest.of(0, 1))
                .stream()
                .findFirst()
                .orElseGet(() -> {
                    ResearchSession s = ResearchSession.builder()
                            .user(user)
                            .title("Research Session")
                            .build();
                    return sessionRepository.save(s);
                });
    }

    private ResearchQuery persistQuery(
            ResearchSession session,
            String question,
            String answer,
            Map<String, Object> aiResponse,
            List<Map<String, Object>> verifiedCitations,
            long latencyMs,
            String strategy) {

        String answerJson = toJson(aiResponse);
        String citationsJson = toJson(verifiedCitations);

        ResearchQuery query = ResearchQuery.builder()
                .session(session)
                .question(question)
                .answerText(answer)
                .answerJson(answerJson)
                .citationsJson(citationsJson)
                .latencyMs(latencyMs)
                .retrievalStrategy(strategy)
                .build();

        session.getQueries().add(query);
        sessionRepository.save(session);
        return query;
    }

    private ResearchSessionSummary toSessionSummary(ResearchSession s) {
        return new ResearchSessionSummary(
                s.getId(),
                s.getTitle(),
                s.getDescription(),
                s.getQueries().size(),
                s.getCreatedAt(),
                s.getUpdatedAt()
        );
    }

    private ResearchSessionDetail toSessionDetail(ResearchSession s) {
        List<ResearchQuerySummary> queries = s.getQueries().stream()
                .map(q -> new ResearchQuerySummary(
                        q.getId(),
                        q.getQuestion(),
                        q.getAnswerText(),
                        q.getLatencyMs(),
                        q.getRetrievalStrategy(),
                        q.getCreatedAt()
                ))
                .toList();
        return new ResearchSessionDetail(
                s.getId(), s.getTitle(), s.getDescription(),
                queries, s.getCreatedAt(), s.getUpdatedAt()
        );
    }

    private String toJson(Object obj) {
        try {
            return objectMapper.writeValueAsString(obj);
        } catch (JsonProcessingException ex) {
            log.warn("Failed to serialize to JSON", ex);
            return "{}";
        }
    }

    // ── Phase 3 helpers ───────────────────────────────────────────────────────

    /**
     * Resolve and validate document IDs — returns only those owned by the user.
     * Throws 403 if any requested ID is not owned by the user.
     */
    private List<String> resolveOwnedDocIds(List<UUID> requestedIds, UUID userId) {
        if (requestedIds == null || requestedIds.isEmpty()) {
            return allOwnedDocIds(userId);
        }
        List<Document> owned = documentRepository.findAllByIdInAndOwnerId(requestedIds, userId);
        if (owned.size() < requestedIds.size()) {
            // Some requested IDs don't belong to this user — log and reject
            List<UUID> ownedIds = owned.stream().map(Document::getId).toList();
            List<UUID> forbidden = requestedIds.stream()
                    .filter(id -> !ownedIds.contains(id))
                    .toList();
            log.warn("Owner isolation: user {} requested documents not owned by them: {}",
                    userId, forbidden);
            throw new ResponseStatusException(HttpStatus.FORBIDDEN,
                    "One or more document IDs do not belong to your account.");
        }
        return owned.stream().map(d -> d.getId().toString()).toList();
    }

    /**
     * Return all document IDs owned by the given user.
     * Used when no specific documentIds are requested (corpus-wide search).
     */
    private List<String> allOwnedDocIds(UUID userId) {
        return documentRepository.findAllByOwnerId(userId)
                .stream().map(d -> d.getId().toString()).toList();
    }

    /**
     * Extract verified/invalid citation lists from AI service response.
     * The AI service already runs citation verification; we pass its output through.
     */
    @SuppressWarnings("unchecked")
    private List<Map<String, Object>> extractVerified(Map<String, Object> aiResponse) {
        Object val = aiResponse.get("verified_citations");
        return val instanceof List<?> l ? (List<Map<String, Object>>) l : List.of();
    }

    @SuppressWarnings("unchecked")
    private List<Map<String, Object>> extractInvalid(Map<String, Object> aiResponse) {
        Object val = aiResponse.get("invalid_citations");
        return val instanceof List<?> l ? (List<Map<String, Object>>) l : List.of();
    }

    private String extractConfidence(Map<String, Object> aiResponse) {
        Object val = aiResponse.get("confidence");
        return val instanceof String s ? s : "MEDIUM";
    }

    private int extractRetrievedChunks(Map<String, Object> aiResponse) {
        Object val = aiResponse.get("retrieved_chunks");
        return val instanceof Number n ? n.intValue() : 0;
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> extractStructured(Map<String, Object> aiResponse, String key) {
        Object val = aiResponse.get(key);
        return val instanceof Map<?, ?> m ? (Map<String, Object>) m : aiResponse;
    }

    @SuppressWarnings("unchecked")
    private List<Map<String, Object>> extractPrecedents(Map<String, Object> aiResponse) {
        Object val = aiResponse.get("precedents");
        return val instanceof List<?> l ? (List<Map<String, Object>>) l : List.of();
    }

    // ── Phase 3 response builders ─────────────────────────────────────────────

    private CaseComparisonResponse buildComparisonResponse(
            String question, Map<String, Object> aiResponse, long latencyMs) {
        return new CaseComparisonResponse(
                question,
                extractStructured(aiResponse, "structured_comparison"),
                extractVerified(aiResponse),
                extractInvalid(aiResponse),
                extractConfidence(aiResponse),
                latencyMs,
                Instant.now(),
                CaseComparisonResponse.LEGAL_DISCLAIMER
        );
    }

    private PrecedentSearchResponse buildPrecedentResponse(
            String query, Map<String, Object> aiResponse, long latencyMs) {
        return new PrecedentSearchResponse(
                query,
                extractPrecedents(aiResponse),
                extractVerified(aiResponse),
                extractInvalid(aiResponse),
                extractRetrievedChunks(aiResponse),
                extractConfidence(aiResponse),
                latencyMs,
                Instant.now(),
                PrecedentSearchResponse.LEGAL_DISCLAIMER
        );
    }

    private ProvisionAnalysisResponse buildProvisionResponse(
            String provision, Map<String, Object> aiResponse, long latencyMs) {
        return new ProvisionAnalysisResponse(
                provision,
                extractStructured(aiResponse, "structured_analysis"),
                extractVerified(aiResponse),
                extractInvalid(aiResponse),
                extractConfidence(aiResponse),
                latencyMs,
                Instant.now(),
                ProvisionAnalysisResponse.LEGAL_DISCLAIMER
        );
    }

    private ResearchBriefResponse buildBriefResponse(
            String question, Map<String, Object> aiResponse, long latencyMs) {
        return new ResearchBriefResponse(
                question,
                extractStructured(aiResponse, "structured_brief"),
                extractVerified(aiResponse),
                extractInvalid(aiResponse),
                extractRetrievedChunks(aiResponse),
                extractConfidence(aiResponse),
                latencyMs,
                Instant.now(),
                ResearchBriefResponse.LEGAL_DISCLAIMER
        );
    }
}
