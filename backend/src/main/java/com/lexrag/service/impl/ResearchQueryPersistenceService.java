package com.lexrag.service.impl;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.lexrag.domain.entities.ResearchQuery;
import com.lexrag.domain.entities.ResearchSession;
import com.lexrag.domain.entities.User;
import com.lexrag.domain.repositories.ResearchSessionRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Map;

/**
 * Persists completed research query results in a short, dedicated transaction.
 *
 * Kept as a separate Spring bean (rather than a method on {@link ResearchServiceImpl})
 * so that {@code @Transactional} actually applies via Spring's AOP proxy — a
 * same-class ("this.") call would bypass the proxy and silently run without a
 * transaction. This mirrors the pattern already used by
 * {@link IngestionCoordinator} for the same reason.
 *
 * Deliberately NOT wrapping the AI service call itself: that call can take up
 * to five minutes (see AiServiceClient.GENERATE_TIMEOUT), and holding a DB
 * transaction/connection open for that whole duration would starve the
 * connection pool under concurrent load. Callers fetch the AI response first,
 * outside any transaction, then hand the result here to persist quickly.
 */
@Component
@RequiredArgsConstructor
@Slf4j
public class ResearchQueryPersistenceService {

    private final ResearchSessionRepository sessionRepository;
    private final ObjectMapper objectMapper;

    @Transactional
    public ResearchQuery save(
            User user,
            String question,
            String answer,
            Map<String, Object> aiResponse,
            List<Map<String, Object>> verifiedCitations,
            long latencyMs,
            String strategy) {

        ResearchSession session = getOrCreateDefaultSession(user);

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

    private String toJson(Object obj) {
        try {
            return objectMapper.writeValueAsString(obj);
        } catch (JsonProcessingException ex) {
            log.warn("Failed to serialize to JSON", ex);
            return "{}";
        }
    }
}
