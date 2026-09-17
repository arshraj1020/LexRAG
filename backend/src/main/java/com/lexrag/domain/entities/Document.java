package com.lexrag.domain.entities;

import com.lexrag.domain.enums.DocumentStatus;
import jakarta.persistence.*;
import lombok.*;
import org.springframework.data.annotation.CreatedDate;
import org.springframework.data.annotation.LastModifiedDate;
import org.springframework.data.jpa.domain.support.AuditingEntityListener;

import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "documents", indexes = {
        @Index(name = "idx_documents_owner", columnList = "owner_id"),
        @Index(name = "idx_documents_status", columnList = "status")
})
@EntityListeners(AuditingEntityListener.class)
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class Document {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "owner_id", nullable = false)
    private User owner;

    @Column(nullable = false, length = 255)
    private String originalFilename;

    /** Path relative to the upload directory. Never expose full server path to clients. */
    @Column(nullable = false, length = 512)
    private String storagePath;

    @Column(nullable = false)
    private Long fileSizeBytes;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 20)
    @Builder.Default
    private DocumentStatus status = DocumentStatus.UPLOADED;

    /** Human-readable error if status = FAILED. */
    @Column(columnDefinition = "TEXT")
    private String errorMessage;

    /** Display title — defaults to filename, editable by user. */
    @Column(nullable = false, length = 255)
    private String title;

    // ── Extracted Legal Metadata ──────────────────────────
    @Column(length = 500)
    private String caseName;

    @Column(length = 200)
    private String court;

    @Column(length = 100)
    private String jurisdiction;

    @Column(length = 100)
    private String caseNumber;

    @Column(length = 50)
    private String caseYear;

    @Column(length = 500)
    private String judges;

    @Column(length = 100)
    private String documentType;

    @Column(length = 10)
    private String language;

    private Integer pageCount;

    /** Total text chunks stored in pgvector after processing. */
    private Integer chunkCount;

    @CreatedDate
    @Column(nullable = false, updatable = false)
    private Instant createdAt;

    @LastModifiedDate
    @Column(nullable = false)
    private Instant updatedAt;

    /** Set when processing completes (success or failure). */
    private Instant processedAt;
}
