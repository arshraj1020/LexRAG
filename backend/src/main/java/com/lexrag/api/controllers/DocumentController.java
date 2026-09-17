package com.lexrag.api.controllers;

import com.lexrag.api.dto.response.DocumentResponse;
import com.lexrag.api.dto.response.PageResponse;
import com.lexrag.domain.entities.User;
import com.lexrag.domain.repositories.UserRepository;
import com.lexrag.service.interfaces.DocumentService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.core.userdetails.UsernameNotFoundException;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.util.UUID;

@RestController
@RequestMapping("/api/documents")
@RequiredArgsConstructor
@Tag(name = "Documents", description = "Upload, list, view and delete legal documents")
public class DocumentController {

    private final DocumentService documentService;
    private final UserRepository userRepository;

    @PostMapping(consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    @ResponseStatus(HttpStatus.ACCEPTED)
    @Operation(summary = "Upload a PDF legal document. Processing happens asynchronously.")
    public DocumentResponse upload(
            @RequestParam("file") MultipartFile file,
            @AuthenticationPrincipal UserDetails principal) {

        User owner = resolveUser(principal);
        return documentService.upload(file, owner);
    }

    @GetMapping
    @Operation(summary = "List your documents, newest first")
    public PageResponse<DocumentResponse> list(
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size,
            @AuthenticationPrincipal UserDetails principal) {

        User owner = resolveUser(principal);
        return documentService.listForOwner(owner.getId(), page, Math.min(size, 100));
    }

    @GetMapping("/{id}")
    @Operation(summary = "Get a single document by ID")
    public DocumentResponse get(
            @PathVariable UUID id,
            @AuthenticationPrincipal UserDetails principal) {

        User owner = resolveUser(principal);
        return documentService.getForOwner(id, owner.getId());
    }

    @DeleteMapping("/{id}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    @Operation(summary = "Delete a document and all its chunks")
    public void delete(
            @PathVariable UUID id,
            @AuthenticationPrincipal UserDetails principal) {

        User owner = resolveUser(principal);
        documentService.deleteForOwner(id, owner.getId());
    }

    // ── Helpers ───────────────────────────────────────────────

    private User resolveUser(UserDetails principal) {
        return userRepository.findByEmail(principal.getUsername())
                .orElseThrow(() -> new UsernameNotFoundException(
                        "Authenticated user not found: " + principal.getUsername()));
    }
}
