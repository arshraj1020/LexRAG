package com.lexrag.domain.enums;

/**
 * Processing lifecycle states for an uploaded legal document.
 */
public enum DocumentStatus {
    /** File received and saved; processing not yet started. */
    UPLOADED,
    /** AI service is actively extracting, chunking, and embedding. */
    PROCESSING,
    /** Document is fully indexed and available for research. */
    READY,
    /** Processing failed; see errorMessage for details. */
    FAILED
}
