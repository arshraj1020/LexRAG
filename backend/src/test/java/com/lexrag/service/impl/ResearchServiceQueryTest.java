package com.lexrag.service.impl;

import com.lexrag.api.dto.request.ResearchQueryRequest;
import com.lexrag.api.dto.response.ResearchQueryResponse;
import com.lexrag.domain.entities.ResearchQuery;
import com.lexrag.domain.entities.ResearchSession;
import com.lexrag.domain.entities.User;
import com.lexrag.domain.repositories.DocumentRepository;
import com.lexrag.domain.repositories.ResearchSessionRepository;
import com.lexrag.service.ai.AiServiceClient;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

/**
 * Unit tests for ResearchServiceImpl.query() covering:
 *  - correct mapping of the AI service response into ResearchQueryResponse
 *  - that persistence is delegated to ResearchQueryPersistenceService (a
 *    separate bean), never called directly on the session repository from
 *    ResearchServiceImpl itself. This guards the fix that moved query()
 *    off @Transactional (to avoid holding a DB connection open for the
 *    duration of a potentially multi-minute AI service call) while keeping
 *    persistence transactional via the separate collaborator bean.
 */
@ExtendWith(MockitoExtension.class)
class ResearchServiceQueryTest {

    @Mock AiServiceClient aiServiceClient;
    @Mock ResearchSessionRepository sessionRepository;
    @Mock DocumentRepository documentRepository;
    @Mock ResearchQueryPersistenceService queryPersistenceService;

    private ResearchServiceImpl service;
    private User user;

    @BeforeEach
    void setUp() {
        service = new ResearchServiceImpl(
                aiServiceClient, sessionRepository, documentRepository, queryPersistenceService);
        user = User.builder().id(UUID.randomUUID()).email("lawyer@lexrag.test").build();
    }

    @Test
    @DisplayName("query() delegates persistence to ResearchQueryPersistenceService, not directly to sessionRepository")
    void delegatesPersistenceToCollaboratorBean() {
        ResearchQueryRequest request = new ResearchQueryRequest(
                "What is the standard of proof for bail applications?",
                null, "HYBRID_RERANK", null, null, null
        );

        Map<String, Object> aiResponse = Map.of(
                "answer", "The standard is a prima facie case.",
                "verified_citations", List.of(Map.of("citation_id", "X")),
                "confidence", 0.9,
                "retrieved_chunks", 3
        );
        when(aiServiceClient.generate(any())).thenReturn(aiResponse);

        ResearchSession session = ResearchSession.builder().id(UUID.randomUUID()).user(user).build();
        ResearchQuery savedQuery = ResearchQuery.builder()
                .id(UUID.randomUUID())
                .session(session)
                .question(request.question())
                .createdAt(Instant.now())
                .build();
        when(queryPersistenceService.save(any(), any(), any(), any(), any(), anyLong(), any()))
                .thenReturn(savedQuery);

        ResearchQueryResponse response = service.query(request, user);

        assertThat(response.answer()).isEqualTo("The standard is a prima facie case.");
        assertThat(response.confidence()).isEqualTo(0.9);
        assertThat(response.retrievedChunks()).isEqualTo(3);
        assertThat(response.queryId()).isEqualTo(savedQuery.getId());

        verify(queryPersistenceService).save(
                eq(user), eq(request.question()), eq("The standard is a prima facie case."),
                eq(aiResponse), any(), anyLong(), eq("HYBRID_RERANK"));
        verifyNoInteractions(sessionRepository);
    }

    @Test
    @DisplayName("query() returns empty answer/citations gracefully when AI response omits them")
    void handlesSparseAiResponse() {
        ResearchQueryRequest request = new ResearchQueryRequest(
                "What constitutes contempt of court?",
                null, null, null, null, null
        );

        when(aiServiceClient.generate(any())).thenReturn(Map.of());

        ResearchSession session = ResearchSession.builder().id(UUID.randomUUID()).user(user).build();
        ResearchQuery savedQuery = ResearchQuery.builder()
                .id(UUID.randomUUID())
                .session(session)
                .question(request.question())
                .createdAt(Instant.now())
                .build();
        when(queryPersistenceService.save(any(), any(), any(), any(), any(), anyLong(), any()))
                .thenReturn(savedQuery);

        ResearchQueryResponse response = service.query(request, user);

        assertThat(response.answer()).isEqualTo("");
        assertThat(response.confidence()).isNull();
        assertThat(response.retrievedChunks()).isNull();
        assertThat(response.strategy()).isEqualTo("HYBRID_RERANK"); // default from effectiveStrategy()
    }
}
