package com.lexrag.domain.repositories;

import com.lexrag.domain.entities.ResearchSession;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.Optional;
import java.util.UUID;

@Repository
public interface ResearchSessionRepository extends JpaRepository<ResearchSession, UUID> {
    Page<ResearchSession> findByUserIdOrderByCreatedAtDesc(UUID userId, Pageable pageable);
    Optional<ResearchSession> findByIdAndUserId(UUID id, UUID userId);
}
