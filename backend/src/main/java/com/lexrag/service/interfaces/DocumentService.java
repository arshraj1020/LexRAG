package com.lexrag.service.interfaces;

import com.lexrag.api.dto.response.DocumentResponse;
import com.lexrag.api.dto.response.PageResponse;
import com.lexrag.domain.entities.User;
import org.springframework.web.multipart.MultipartFile;

import java.util.UUID;

public interface DocumentService {

    /** Upload a PDF, save to disk, record in DB, trigger async ingestion. */
    DocumentResponse upload(MultipartFile file, User owner);

    /** List the caller's own documents, newest first. */
    PageResponse<DocumentResponse> listForOwner(UUID ownerId, int page, int size);

    /** Get a single document — enforces owner check. */
    DocumentResponse getForOwner(UUID documentId, UUID ownerId);

    /** Delete a document and its chunks — enforces owner check. */
    void deleteForOwner(UUID documentId, UUID ownerId);
}
