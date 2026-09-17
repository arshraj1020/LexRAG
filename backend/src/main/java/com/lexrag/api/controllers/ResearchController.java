package com.lexrag.api.controllers;

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
import com.lexrag.domain.repositories.UserRepository;
import com.lexrag.service.interfaces.ResearchService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.core.userdetails.UsernameNotFoundException;
import org.springframework.web.bind.annotation.*;

import java.util.UUID;

@RestController
@RequestMapping("/api/research")
@RequiredArgsConstructor
@Tag(name = "Research", description = "AI-powered legal research with citation verification")
public class ResearchController {

    private final ResearchService researchService;
    private final UserRepository userRepository;

    @PostMapping("/query")
    @Operation(
        summary = "Submit a legal research question",
        description = "Runs the full RAG pipeline: retrieval → reranking → LLM → citation verification. " +
                      "Strategy defaults to HYBRID_RERANK. Latency 5–60s depending on model and document size."
    )
    public ResearchQueryResponse query(
            @Valid @RequestBody ResearchQueryRequest request,
            @AuthenticationPrincipal UserDetails principal) {

        User user = resolveUser(principal);
        return researchService.query(request, user);
    }

    @GetMapping("/sessions")
    @Operation(
        summary = "List research sessions",
        description = "Returns paginated list of this user's research sessions, newest first."
    )
    public PageResponse<ResearchService.ResearchSessionSummary> listSessions(
            @RequestParam(defaultValue = "0") @Min(0) int page,
            @RequestParam(defaultValue = "20") @Min(1) @Max(50) int size,
            @AuthenticationPrincipal UserDetails principal) {

        User user = resolveUser(principal);
        return researchService.listSessions(user.getId(), page, size);
    }

    @GetMapping("/sessions/{sessionId}")
    @Operation(
        summary = "Get a research session with its query history",
        description = "Returns a session's full query/answer history. Only accessible by the owner."
    )
    public ResearchService.ResearchSessionDetail getSession(
            @PathVariable UUID sessionId,
            @AuthenticationPrincipal UserDetails principal) {

        User user = resolveUser(principal);
        return researchService.getSession(sessionId, user.getId());
    }

    // ── Phase 3 endpoints ─────────────────────────────────────────────────────

    @PostMapping("/compare")
    @Operation(
        summary = "Compare two or more legal cases",
        description = "Runs multi-document retrieval and structured comparison via the LLM. "
                    + "Requires at least 2 documentIds owned by the authenticated user. "
                    + "Returns structured JSON: cases, facts, issues, arguments, reasoning, "
                    + "similarities, differences, conflicting findings. Latency 15–120s."
    )
    public CaseComparisonResponse compare(
            @Valid @RequestBody CaseComparisonRequest request,
            @AuthenticationPrincipal UserDetails principal) {

        User user = resolveUser(principal);
        return researchService.compare(request, user);
    }

    @PostMapping("/precedents")
    @Operation(
        summary = "Search for relevant legal precedents",
        description = "Uses hybrid retrieval + cross-encoder reranking to find the most relevant "
                    + "precedents for the given legal question. Applies optional metadata filters "
                    + "(court, jurisdiction, year). Enforces owner isolation. Latency 10–60s."
    )
    public PrecedentSearchResponse precedents(
            @Valid @RequestBody PrecedentSearchRequest request,
            @AuthenticationPrincipal UserDetails principal) {

        User user = resolveUser(principal);
        return researchService.findPrecedents(request, user);
    }

    @PostMapping("/provision")
    @Operation(
        summary = "Analyse how courts have interpreted a statutory provision",
        description = "Retrieves cases discussing the given statutory provision and produces a "
                    + "structured analysis: key principles, judicial interpretation, cases, "
                    + "scope, and open questions. Does not present generated text as law. "
                    + "Enforces owner isolation. Latency 10–60s."
    )
    public ProvisionAnalysisResponse provision(
            @Valid @RequestBody ProvisionAnalysisRequest request,
            @AuthenticationPrincipal UserDetails principal) {

        User user = resolveUser(principal);
        return researchService.analyseProvision(request, user);
    }

    @PostMapping("/brief")
    @Operation(
        summary = "Generate a structured legal research brief",
        description = "Generates a full research brief with executive summary, key findings, "
                    + "relevant authorities, arguments, supporting/conflicting evidence, "
                    + "open questions, and conclusion. All sections are grounded in citations. "
                    + "Supports filters: court, jurisdiction, year, documentType. "
                    + "Enforces owner isolation. Latency 30–180s (larger context)."
    )
    public ResearchBriefResponse brief(
            @Valid @RequestBody ResearchBriefRequest request,
            @AuthenticationPrincipal UserDetails principal) {

        User user = resolveUser(principal);
        return researchService.generateBrief(request, user);
    }

    // ── Helpers ───────────────────────────────────────────────

    private User resolveUser(UserDetails principal) {
        return userRepository.findByEmail(principal.getUsername())
                .orElseThrow(() -> new UsernameNotFoundException(
                        "Authenticated user not found: " + principal.getUsername()));
    }
}
