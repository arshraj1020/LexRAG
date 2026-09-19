package com.lexrag.service.impl;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.lexrag.api.dto.request.CaseComparisonRequest;
import com.lexrag.api.dto.request.PrecedentSearchRequest;
import com.lexrag.api.dto.request.ProvisionAnalysisRequest;
import com.lexrag.api.dto.request.ResearchBriefRequest;
import com.lexrag.api.dto.response.CaseComparisonResponse;
import com.lexrag.api.dto.response.PrecedentSearchResponse;
import com.lexrag.api.dto.response.ProvisionAnalysisResponse;
import com.lexrag.api.dto.response.ResearchBriefResponse;
import com.lexrag.domain.entities.Document;
import com.lexrag.domain.entities.User;
import com.lexrag.domain.repositories.DocumentRepository;
import com.lexrag.domain.repositories.ResearchSessionRepository;
import com.lexrag.service.ai.AiServiceClient;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.web.server.ResponseStatusException;

import java.util.List;
import java.util.Map;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.*;

/**
 * Unit tests for Phase 3 ResearchServiceImpl methods.
 *
 * Covers:
 *   - compare()   : owner isolation, INSUFFICIENT_EVIDENCE, response mapping
 *   - findPrecedents() : corpus-wide search when no docIds provided, response mapping
 *   - analyseProvision() : owner isolation, response mapping
 *   - generateBrief()   : owner isolation, response mapping
 *   - resolveOwnedDocIds() : throws 403 when a foreign doc ID is requested
 */
@ExtendWith(MockitoExtension.class)
class ResearchServicePhase3Test {

    @Mock AiServiceClient aiServiceClient;
    @Mock ResearchSessionRepository sessionRepository;
    @Mock DocumentRepository documentRepository;
    @Mock ObjectMapper objectMapper;   // not used in Phase 3 paths

    @InjectMocks ResearchServiceImpl service;

    private User user;
    private UUID userId;
    private UUID doc1Id;
    private UUID doc2Id;
    private Document doc1;
    private Document doc2;

    @BeforeEach
    void setUp() {
        userId = UUID.randomUUID();
        doc1Id = UUID.randomUUID();
        doc2Id = UUID.randomUUID();

        user = User.builder()
                .id(userId)
                .email("lawyer@lexrag.test")
                .fullName("Test Lawyer")
                .build();

        doc1 = new Document();
        doc1.setId(doc1Id);

        doc2 = new Document();
        doc2.setId(doc2Id);
    }

    // ── Owner isolation helpers ───────────────────────────────────────────────

    private Map<String, Object> emptyAiResponse() {
        return Map.of(
                "verified_citations", List.of(),
                "invalid_citations", List.of(),
                "confidence", "MEDIUM",
                "retrieved_chunks", 0
        );
    }

    /**
     * Mirrors what the AI service actually sends on its INSUFFICIENT_EVIDENCE /
     * GENERATION_ERROR paths (see ai-service routes.py): the structured_* key
     * is present but explicitly null, alongside other top-level keys like
     * "error"/"explanation". Uses HashMap since Map.of() rejects null values.
     */
    private Map<String, Object> insufficientEvidenceAiResponse(String structuredKey) {
        Map<String, Object> m = new java.util.HashMap<>();
        m.put(structuredKey, null);
        m.put("error", "INSUFFICIENT_EVIDENCE");
        m.put("explanation", "No relevant evidence found in the specified documents.");
        m.put("verified_citations", List.of());
        m.put("invalid_citations", List.of());
        return m;
    }

    private Map<String, Object> aiResponseWithCitations() {
        return Map.of(
                "verified_citations", List.of(
                        Map.of("citation_id", "DOC_ABCD1234_P1_PAR1", "is_valid", true,
                               "claim", "Court held X", "page", 1, "paragraph", 1)
                ),
                "invalid_citations", List.of(),
                "confidence", "HIGH",
                "retrieved_chunks", 5,
                "structured_comparison", Map.of("summary", "No material difference"),
                "structured_analysis", Map.of("principles", List.of()),
                "structured_brief", Map.of("executive_summary", "Brief summary"),
                "precedents", List.of(
                        Map.of("rank", 1, "citation_id", "DOC_ABCD1234_P1_PAR1",
                               "case_name", "State v. Accused")
                )
        );
    }

    // ── compare() ────────────────────────────────────────────────────────────

    @Nested
    @DisplayName("compare()")
    class CompareTests {

        @Test
        @DisplayName("403 when any requested document is foreign")
        void throwsForbiddenForForeignDocuments() {
            UUID foreignId = UUID.randomUUID();
            CaseComparisonRequest request = new CaseComparisonRequest(
                    "Compare these cases about bail",
                    List.of(doc1Id, foreignId),
                    null, null, null
            );

            // Only doc1 is owned
            when(documentRepository.findAllByIdInAndOwnerId(
                    eq(List.of(doc1Id, foreignId)), eq(userId)))
                    .thenReturn(List.of(doc1));   // returned 1 instead of 2

            assertThatThrownBy(() -> service.compare(request, user))
                    .isInstanceOf(ResponseStatusException.class)
                    .hasMessageContaining("do not belong to your account");
        }

        @Test
        @DisplayName("passes verified doc IDs to AI service")
        void passesOwnedDocIdsToAiService() {
            CaseComparisonRequest request = new CaseComparisonRequest(
                    "Compare these two bail cases",
                    List.of(doc1Id, doc2Id),
                    null, null, null
            );

            when(documentRepository.findAllByIdInAndOwnerId(
                    eq(List.of(doc1Id, doc2Id)), eq(userId)))
                    .thenReturn(List.of(doc1, doc2));

            when(aiServiceClient.compare(any())).thenReturn(aiResponseWithCitations());

            CaseComparisonResponse resp = service.compare(request, user);

            assertThat(resp.question()).isEqualTo("Compare these two bail cases");
            assertThat(resp.verifiedCitations()).hasSize(1);
            assertThat(resp.invalidCitations()).isEmpty();
            assertThat(resp.disclaimer()).isNotBlank();
        }

        @Test
        @DisplayName("structuredComparison is null (not the raw AI response) when AI returns explicit null")
        void structuredComparisonIsNullNotRawResponseOnInsufficientEvidence() {
            CaseComparisonRequest request = new CaseComparisonRequest(
                    "Compare these cases about bail",
                    List.of(doc1Id, doc2Id),
                    null, null, null
            );

            when(documentRepository.findAllByIdInAndOwnerId(any(), eq(userId)))
                    .thenReturn(List.of(doc1, doc2));
            when(aiServiceClient.compare(any()))
                    .thenReturn(insufficientEvidenceAiResponse("structured_comparison"));

            CaseComparisonResponse resp = service.compare(request, user);

            // Regression: this used to fall back to dumping the entire raw AI
            // response (including "error"/"explanation" keys) into this field.
            assertThat(resp.structuredComparison()).isNull();
        }

        @Test
        @DisplayName("returns empty citations when AI returns none")
        void returnsEmptyCitationsOnInsufficientEvidence() {
            CaseComparisonRequest request = new CaseComparisonRequest(
                    "Compare these cases in detail",
                    List.of(doc1Id, doc2Id),
                    "High Court", 2020, 2024
            );

            when(documentRepository.findAllByIdInAndOwnerId(any(), eq(userId)))
                    .thenReturn(List.of(doc1, doc2));

            when(aiServiceClient.compare(any())).thenReturn(emptyAiResponse());

            CaseComparisonResponse resp = service.compare(request, user);

            assertThat(resp.verifiedCitations()).isEmpty();
            assertThat(resp.invalidCitations()).isEmpty();
        }

        @Test
        @DisplayName("passes metadata filters to AI service")
        void passesFiltersToAiService() {
            CaseComparisonRequest request = new CaseComparisonRequest(
                    "Compare these bail cases",
                    List.of(doc1Id, doc2Id),
                    "Supreme Court", 2018, 2023
            );

            when(documentRepository.findAllByIdInAndOwnerId(any(), eq(userId)))
                    .thenReturn(List.of(doc1, doc2));

            when(aiServiceClient.compare(any())).thenReturn(emptyAiResponse());

            service.compare(request, user);

            verify(aiServiceClient).compare(argThat(r ->
                    "Supreme Court".equals(r.court())
                    && Integer.valueOf(2018).equals(r.yearFrom())
                    && Integer.valueOf(2023).equals(r.yearTo())
            ));
        }
    }

    // ── findPrecedents() ──────────────────────────────────────────────────────

    @Nested
    @DisplayName("findPrecedents()")
    class FindPrecedentsTests {

        @Test
        @DisplayName("corpus-wide search when no documentIds provided")
        void corpusWideSearchWhenNoDocIds() {
            PrecedentSearchRequest request = new PrecedentSearchRequest(
                    "bail in murder cases under Section 302",
                    null,   // no document IDs → use all owned
                    null, null, null, null, null
            );

            when(documentRepository.findAllByOwnerId(userId))
                    .thenReturn(List.of(doc1, doc2));
            when(aiServiceClient.findPrecedents(any())).thenReturn(emptyAiResponse());

            PrecedentSearchResponse resp = service.findPrecedents(request, user);

            verify(documentRepository).findAllByOwnerId(userId);
            verify(documentRepository, never()).findAllByIdInAndOwnerId(any(), any());
            assertThat(resp.precedents()).isEmpty();
        }

        @Test
        @DisplayName("403 when any requested document is foreign")
        void throwsForbiddenForForeignDocuments() {
            UUID foreignId = UUID.randomUUID();
            PrecedentSearchRequest request = new PrecedentSearchRequest(
                    "precedent query",
                    List.of(doc1Id, foreignId),
                    null, null, null, null, null
            );

            when(documentRepository.findAllByIdInAndOwnerId(
                    eq(List.of(doc1Id, foreignId)), eq(userId)))
                    .thenReturn(List.of(doc1));  // missing foreignId

            assertThatThrownBy(() -> service.findPrecedents(request, user))
                    .isInstanceOf(ResponseStatusException.class)
                    .hasMessageContaining("do not belong to your account");
        }

        @Test
        @DisplayName("precedents list is returned from AI response")
        void precedentsExtractedFromAiResponse() {
            PrecedentSearchRequest request = new PrecedentSearchRequest(
                    "bail conditions precedent",
                    List.of(doc1Id),
                    null, null, null, null, 5
            );

            when(documentRepository.findAllByIdInAndOwnerId(any(), eq(userId)))
                    .thenReturn(List.of(doc1));
            when(aiServiceClient.findPrecedents(any())).thenReturn(aiResponseWithCitations());

            PrecedentSearchResponse resp = service.findPrecedents(request, user);

            assertThat(resp.precedents()).hasSize(1);
            assertThat(resp.verifiedCitations()).hasSize(1);
            assertThat(resp.confidence()).isEqualTo("HIGH");
        }
    }

    // ── analyseProvision() ────────────────────────────────────────────────────

    @Nested
    @DisplayName("analyseProvision()")
    class AnalyseProvisionTests {

        @Test
        @DisplayName("403 when any requested document is foreign")
        void throwsForbiddenForForeignDocuments() {
            UUID foreignId = UUID.randomUUID();
            ProvisionAnalysisRequest request = new ProvisionAnalysisRequest(
                    "Section 302 IPC — murder",
                    List.of(doc1Id, foreignId),
                    null, null, null
            );

            when(documentRepository.findAllByIdInAndOwnerId(any(), eq(userId)))
                    .thenReturn(List.of(doc1));

            assertThatThrownBy(() -> service.analyseProvision(request, user))
                    .isInstanceOf(ResponseStatusException.class)
                    .hasMessageContaining("do not belong to your account");
        }

        @Test
        @DisplayName("structuredAnalysis is null (not the raw AI response) when AI returns explicit null")
        void structuredAnalysisIsNullNotRawResponseOnInsufficientEvidence() {
            ProvisionAnalysisRequest request = new ProvisionAnalysisRequest(
                    "Section 302 IPC",
                    null, null, null, null
            );

            when(documentRepository.findAllByOwnerId(userId)).thenReturn(List.of(doc1));
            when(aiServiceClient.analyseProvision(any()))
                    .thenReturn(insufficientEvidenceAiResponse("structured_analysis"));

            ProvisionAnalysisResponse resp = service.analyseProvision(request, user);

            assertThat(resp.structuredAnalysis()).isNull();
        }

        @Test
        @DisplayName("response has correct provision text and disclaimer")
        void responseHasCorrectFields() {
            ProvisionAnalysisRequest request = new ProvisionAnalysisRequest(
                    "Section 302 IPC",
                    null,   // corpus-wide
                    null, null, null
            );

            when(documentRepository.findAllByOwnerId(userId)).thenReturn(List.of(doc1));
            when(aiServiceClient.analyseProvision(any())).thenReturn(aiResponseWithCitations());

            ProvisionAnalysisResponse resp = service.analyseProvision(request, user);

            assertThat(resp.provision()).isEqualTo("Section 302 IPC");
            assertThat(resp.disclaimer()).isNotBlank();
            assertThat(resp.verifiedCitations()).hasSize(1);
        }
    }

    // ── generateBrief() ───────────────────────────────────────────────────────

    @Nested
    @DisplayName("generateBrief()")
    class GenerateBriefTests {

        @Test
        @DisplayName("403 when any requested document is foreign")
        void throwsForbiddenForForeignDocuments() {
            UUID foreignId = UUID.randomUUID();
            ResearchBriefRequest request = new ResearchBriefRequest(
                    "standard of proof in contempt proceedings",
                    List.of(doc1Id, foreignId),
                    null, null, null, null, null
            );

            when(documentRepository.findAllByIdInAndOwnerId(any(), eq(userId)))
                    .thenReturn(List.of(doc1));

            assertThatThrownBy(() -> service.generateBrief(request, user))
                    .isInstanceOf(ResponseStatusException.class)
                    .hasMessageContaining("do not belong to your account");
        }

        @Test
        @DisplayName("corpus-wide search when no documentIds provided")
        void corpusWideSearchWhenNoDocIds() {
            ResearchBriefRequest request = new ResearchBriefRequest(
                    "contempt of court principles",
                    null,
                    null, null, null, null, null
            );

            when(documentRepository.findAllByOwnerId(userId)).thenReturn(List.of(doc1));
            when(aiServiceClient.generateBrief(any())).thenReturn(emptyAiResponse());

            service.generateBrief(request, user);

            verify(documentRepository).findAllByOwnerId(userId);
            verify(documentRepository, never()).findAllByIdInAndOwnerId(any(), any());
        }

        @Test
        @DisplayName("structuredBrief is null (not the raw AI response) when AI returns explicit null")
        void structuredBriefIsNullNotRawResponseOnInsufficientEvidence() {
            ResearchBriefRequest request = new ResearchBriefRequest(
                    "When may bail be denied for economic offences?",
                    null, null, null, null, null, null
            );

            when(documentRepository.findAllByOwnerId(userId)).thenReturn(List.of(doc1));
            when(aiServiceClient.generateBrief(any()))
                    .thenReturn(insufficientEvidenceAiResponse("structured_brief"));

            ResearchBriefResponse resp = service.generateBrief(request, user);

            assertThat(resp.structuredBrief()).isNull();
        }

        @Test
        @DisplayName("response has correct research question and disclaimer")
        void responseHasCorrectFields() {
            ResearchBriefRequest request = new ResearchBriefRequest(
                    "When may bail be denied for economic offences?",
                    null,
                    null, null, null, null, null
            );

            when(documentRepository.findAllByOwnerId(userId)).thenReturn(List.of(doc1));
            when(aiServiceClient.generateBrief(any())).thenReturn(aiResponseWithCitations());

            ResearchBriefResponse resp = service.generateBrief(request, user);

            assertThat(resp.researchQuestion()).isEqualTo("When may bail be denied for economic offences?");
            assertThat(resp.disclaimer()).isNotBlank();
            assertThat(resp.retrievedChunks()).isEqualTo(5);
        }

        @Test
        @DisplayName("passes jurisdiction and documentType to AI service")
        void passesJurisdictionAndDocumentType() {
            ResearchBriefRequest request = new ResearchBriefRequest(
                    "constitutional validity of detention",
                    null,
                    "Supreme Court", "Supreme Court of India", 2010, 2024, "judgment"
            );

            when(documentRepository.findAllByOwnerId(userId)).thenReturn(List.of(doc1));
            when(aiServiceClient.generateBrief(any())).thenReturn(emptyAiResponse());

            service.generateBrief(request, user);

            verify(aiServiceClient).generateBrief(argThat(r ->
                    "Supreme Court of India".equals(r.jurisdiction())
                    && "judgment".equals(r.documentType())
            ));
        }
    }

    // ── Cross-cutting: resolveOwnedDocIds ─────────────────────────────────────

    @Nested
    @DisplayName("resolveOwnedDocIds (owner isolation)")
    class OwnerIsolationTests {

        @Test
        @DisplayName("all requested IDs owned → returns all as strings")
        void allOwnedIdsReturned() {
            // Use compare() as the driver for resolveOwnedDocIds
            CaseComparisonRequest request = new CaseComparisonRequest(
                    "Compare bail standards",
                    List.of(doc1Id, doc2Id),
                    null, null, null
            );

            when(documentRepository.findAllByIdInAndOwnerId(any(), eq(userId)))
                    .thenReturn(List.of(doc1, doc2));
            when(aiServiceClient.compare(any())).thenReturn(emptyAiResponse());

            // Should not throw
            CaseComparisonResponse resp = service.compare(request, user);
            assertThat(resp).isNotNull();

            // Verify the AI client was called with string representations of both UUIDs
            verify(aiServiceClient).compare(argThat(r ->
                    r.documentIds().contains(doc1Id.toString())
                    && r.documentIds().contains(doc2Id.toString())
            ));
        }

        @Test
        @DisplayName("partial ownership → throws 403")
        void partialOwnershipThrows403() {
            UUID foreign1 = UUID.randomUUID();
            UUID foreign2 = UUID.randomUUID();

            CaseComparisonRequest request = new CaseComparisonRequest(
                    "Compare three cases",
                    List.of(doc1Id, foreign1, foreign2),
                    null, null, null
            );

            // Only doc1 is returned (2 foreign IDs missing)
            when(documentRepository.findAllByIdInAndOwnerId(any(), eq(userId)))
                    .thenReturn(List.of(doc1));

            assertThatThrownBy(() -> service.compare(request, user))
                    .isInstanceOf(ResponseStatusException.class)
                    .satisfies(ex -> {
                        ResponseStatusException rse = (ResponseStatusException) ex;
                        assertThat(rse.getStatusCode().value()).isEqualTo(403);
                    });
        }
    }
}
