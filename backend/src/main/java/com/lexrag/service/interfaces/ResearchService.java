package com.lexrag.service.interfaces;

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
import com.lexrag.domain.entities.User;

import java.util.UUID;

public interface ResearchService {

    /**
     * Execute a RAG research query and persist the result.
     *
     * Calls the AI service for retrieval + generation, verifies citations,
     * saves the query+answer to research_queries, and returns the response.
     */
    ResearchQueryResponse query(ResearchQueryRequest request, User user);

    /**
     * List research sessions for a user (newest first, paginated).
     */
    PageResponse<ResearchSessionSummary> listSessions(UUID userId, int page, int size);

    /**
     * Get a single session with its full query history.
     * Enforces owner isolation — throws ResourceNotFoundException if not owned by userId.
     */
    ResearchSessionDetail getSession(UUID sessionId, UUID userId);

    // ── Phase 3 methods ───────────────────────────────────────────────────────

    /**
     * Compare two or more legal cases.
     * Enforces owner isolation — documentIds must belong to the requesting user.
     */
    CaseComparisonResponse compare(CaseComparisonRequest request, User user);

    /**
     * Find relevant precedents using hybrid retrieval + reranking.
     * Enforces owner isolation on documentIds.
     */
    PrecedentSearchResponse findPrecedents(PrecedentSearchRequest request, User user);

    /**
     * Analyse how courts have interpreted a statutory provision.
     * Enforces owner isolation on documentIds.
     */
    ProvisionAnalysisResponse analyseProvision(ProvisionAnalysisRequest request, User user);

    /**
     * Generate a structured legal research brief.
     * Enforces owner isolation on documentIds.
     */
    ResearchBriefResponse generateBrief(ResearchBriefRequest request, User user);

    // ── Inner response types ───────────────────────────────────

    record ResearchSessionSummary(
            UUID id,
            String title,
            String description,
            int queryCount,
            java.time.Instant createdAt,
            java.time.Instant updatedAt
    ) {}

    record ResearchQuerySummary(
            UUID id,
            String question,
            String answerText,
            Long latencyMs,
            String retrievalStrategy,
            java.time.Instant createdAt
    ) {}

    record ResearchSessionDetail(
            UUID id,
            String title,
            String description,
            java.util.List<ResearchQuerySummary> queries,
            java.time.Instant createdAt,
            java.time.Instant updatedAt
    ) {}
}
