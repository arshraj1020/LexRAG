package com.lexrag.domain.repositories;

import com.lexrag.domain.entities.Document;
import com.lexrag.domain.enums.DocumentStatus;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.Optional;
import java.util.UUID;

@Repository
public interface DocumentRepository extends JpaRepository<Document, UUID> {

    /** Owner isolation — never allow cross-user access. */
    Page<Document> findByOwnerIdOrderByCreatedAtDesc(UUID ownerId, Pageable pageable);

    Optional<Document> findByIdAndOwnerId(UUID id, UUID ownerId);

    boolean existsByIdAndOwnerId(UUID id, UUID ownerId);

    long countByOwnerIdAndStatus(UUID ownerId, DocumentStatus status);

    /**
     * Fetch all document IDs owned by a user — used by Phase 3 pipelines
     * to build the owner_document_ids set for citation verification.
     */
    java.util.List<Document> findAllByOwnerId(UUID ownerId);

    /**
     * Find all documents by IDs that are also owned by the given user.
     * Used to validate that requested documentIds belong to the caller.
     */
    java.util.List<Document> findAllByIdInAndOwnerId(java.util.Collection<UUID> ids, UUID ownerId);
}
