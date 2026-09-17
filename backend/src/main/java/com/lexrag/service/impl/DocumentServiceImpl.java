package com.lexrag.service.impl;

import com.lexrag.api.dto.response.DocumentResponse;
import com.lexrag.api.dto.response.PageResponse;
import com.lexrag.domain.entities.Document;
import com.lexrag.domain.entities.User;
import com.lexrag.domain.enums.DocumentStatus;
import com.lexrag.domain.repositories.DocumentRepository;
import com.lexrag.exception.ResourceNotFoundException;
import com.lexrag.service.interfaces.DocumentService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardCopyOption;
import java.util.Arrays;
import java.util.UUID;

@Service
@RequiredArgsConstructor
@Slf4j
public class DocumentServiceImpl implements DocumentService {

    private static final long MAX_FILE_SIZE_BYTES = 50L * 1024 * 1024; // 50 MB
    private static final String ALLOWED_MIME_TYPE = "application/pdf";

    private final DocumentRepository documentRepository;
    private final IngestionCoordinator ingestionCoordinator;

    @Value("${upload.directory}")
    private String uploadDirectory;

    @Override
    @Transactional
    public DocumentResponse upload(MultipartFile file, User owner) {
        validateFile(file);

        // Create owner-scoped subdirectory for isolation
        Path ownerDir = Paths.get(uploadDirectory, owner.getId().toString());
        Path storagePath;
        try {
            Files.createDirectories(ownerDir);
            String uniqueName = UUID.randomUUID() + "_" + sanitizeFilename(file.getOriginalFilename());
            storagePath = ownerDir.resolve(uniqueName);
            Files.copy(file.getInputStream(), storagePath, StandardCopyOption.REPLACE_EXISTING);
        } catch (IOException ex) {
            throw new IllegalStateException("Failed to store uploaded file", ex);
        }

        // Derive display title from filename (user can edit later)
        String title = file.getOriginalFilename() != null
                ? file.getOriginalFilename().replaceFirst("\\.pdf$", "")
                : "Untitled Document";

        Document document = Document.builder()
                .owner(owner)
                .originalFilename(file.getOriginalFilename())
                .storagePath(storagePath.toString())
                .fileSizeBytes(file.getSize())
                .title(title)
                .status(DocumentStatus.UPLOADED)
                .build();

        document = documentRepository.save(document);
        log.info("Saved document {} for owner {}", document.getId(), owner.getId());

        // Trigger async ingestion — updates status independently.
        // Called via IngestionCoordinator (separate @Component) so @Async proxy works.
        ingestionCoordinator.triggerAsync(document.getId().toString(), storagePath.toString());

        return DocumentResponse.from(document);
    }

    @Override
    @Transactional(readOnly = true)
    public PageResponse<DocumentResponse> listForOwner(UUID ownerId, int page, int size) {
        Page<Document> docs = documentRepository.findByOwnerIdOrderByCreatedAtDesc(
                ownerId, PageRequest.of(page, size));
        return PageResponse.from(docs, DocumentResponse::from);
    }

    @Override
    @Transactional(readOnly = true)
    public DocumentResponse getForOwner(UUID documentId, UUID ownerId) {
        Document doc = documentRepository.findByIdAndOwnerId(documentId, ownerId)
                .orElseThrow(() -> new ResourceNotFoundException(
                        "Document not found: " + documentId));
        return DocumentResponse.from(doc);
    }

    @Override
    @Transactional
    public void deleteForOwner(UUID documentId, UUID ownerId) {
        Document doc = documentRepository.findByIdAndOwnerId(documentId, ownerId)
                .orElseThrow(() -> new ResourceNotFoundException(
                        "Document not found: " + documentId));

        // Delete physical file
        try {
            Files.deleteIfExists(Paths.get(doc.getStoragePath()));
        } catch (IOException ex) {
            log.warn("Could not delete file {}: {}", doc.getStoragePath(), ex.getMessage());
        }

        // Cascading delete removes document_chunks (ON DELETE CASCADE in schema)
        documentRepository.delete(doc);
        log.info("Deleted document {} for owner {}", documentId, ownerId);
    }

    // ── Private helpers ───────────────────────────────────────

    // PDF magic bytes: %PDF (0x25 0x50 0x44 0x46)
    private static final byte[] PDF_MAGIC = {0x25, 0x50, 0x44, 0x46};

    private void validateFile(MultipartFile file) {
        if (file == null || file.isEmpty()) {
            throw new IllegalArgumentException("File must not be empty");
        }
        if (file.getSize() > MAX_FILE_SIZE_BYTES) {
            throw new IllegalArgumentException(
                    "File exceeds maximum size of 50 MB");
        }
        String contentType = file.getContentType();
        if (!ALLOWED_MIME_TYPE.equals(contentType)) {
            throw new IllegalArgumentException(
                    "Only PDF files are accepted. Received: " + contentType);
        }
        // Verify file magic bytes — Content-Type header can be spoofed by the client.
        try (InputStream is = file.getInputStream()) {
            byte[] header = is.readNBytes(4);
            if (!Arrays.equals(header, PDF_MAGIC)) {
                throw new IllegalArgumentException(
                        "File content is not a valid PDF (magic bytes mismatch)");
            }
        } catch (IllegalArgumentException ex) {
            throw ex;
        } catch (IOException ex) {
            throw new IllegalStateException("Failed to read file header for validation", ex);
        }
    }

    private String sanitizeFilename(String filename) {
        if (filename == null) return "upload.pdf";
        return filename.replaceAll("[^a-zA-Z0-9._-]", "_");
    }
}
