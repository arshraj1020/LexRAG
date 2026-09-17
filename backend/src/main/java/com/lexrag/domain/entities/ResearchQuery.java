package com.lexrag.domain.entities;

import jakarta.persistence.*;
import lombok.*;
import org.springframework.data.annotation.CreatedDate;
import org.springframework.data.jpa.domain.support.AuditingEntityListener;

import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "research_queries", indexes = {
        @Index(name = "idx_research_queries_session", columnList = "session_id"),
        @Index(name = "idx_research_queries_created", columnList = "created_at")
})
@EntityListeners(AuditingEntityListener.class)
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class ResearchQuery {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "session_id", nullable = false)
    private ResearchSession session;

    @Column(nullable = false, columnDefinition = "TEXT")
    private String question;

    /** Full JSON answer from AI service, stored for history replay. */
    @Column(columnDefinition = "TEXT")
    private String answerJson;

    /** Plain text answer for quick display. */
    @Column(columnDefinition = "TEXT")
    private String answerText;

    /** JSON array of citation objects. */
    @Column(columnDefinition = "TEXT")
    private String citationsJson;

    /** Milliseconds from query receipt to final answer. */
    private Long latencyMs;

    /** Retrieval strategy used (DENSE / HYBRID / HYBRID_RERANK / etc.) */
    @Column(length = 50)
    private String retrievalStrategy;

    @CreatedDate
    @Column(nullable = false, updatable = false)
    private Instant createdAt;
}
