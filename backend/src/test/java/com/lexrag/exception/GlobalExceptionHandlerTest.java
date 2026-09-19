package com.lexrag.exception;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.core.MethodParameter;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;

import java.lang.reflect.Method;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Covers the exception handlers added to close gaps where specific client
 * errors were previously falling through to the generic Exception -> 500
 * handler (e.g. a malformed UUID path variable returning 500 instead of 400).
 */
class GlobalExceptionHandlerTest {

    private final GlobalExceptionHandler handler = new GlobalExceptionHandler();

    @Test
    @DisplayName("malformed path variable (e.g. non-UUID document id) maps to 400, not 500")
    void typeMismatchMapsTo400() throws Exception {
        Method dummy = DummyController.class.getMethod("byId", java.util.UUID.class);
        MethodParameter param = new MethodParameter(dummy, 0);
        MethodArgumentTypeMismatchException ex =
                new MethodArgumentTypeMismatchException("not-a-uuid", java.util.UUID.class, "id", param, null);

        ResponseEntity<GlobalExceptionHandler.ErrorResponse> response = handler.handleTypeMismatch(ex);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.BAD_REQUEST);
        assertThat(response.getBody()).isNotNull();
        assertThat(response.getBody().error()).isEqualTo("TYPE_MISMATCH");
        assertThat(response.getBody().message()).contains("id");
    }

    @Test
    @DisplayName("malformed JSON request body maps to 400, not 500")
    void malformedJsonMapsTo400() {
        HttpMessageNotReadableException ex =
                new HttpMessageNotReadableException("JSON parse error", (org.springframework.http.HttpInputMessage) null);

        ResponseEntity<GlobalExceptionHandler.ErrorResponse> response = handler.handleMalformedJson(ex);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.BAD_REQUEST);
        assertThat(response.getBody()).isNotNull();
        assertThat(response.getBody().error()).isEqualTo("MALFORMED_REQUEST");
    }

    @Test
    @DisplayName("access denied maps to 403, not 500, and does not leak internal detail")
    void accessDeniedMapsTo403() {
        AccessDeniedException ex = new AccessDeniedException("secret internal reason");

        ResponseEntity<GlobalExceptionHandler.ErrorResponse> response = handler.handleAccessDenied(ex);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN);
        assertThat(response.getBody()).isNotNull();
        assertThat(response.getBody().error()).isEqualTo("ACCESS_DENIED");
        assertThat(response.getBody().message()).doesNotContain("secret internal reason");
    }

    @Test
    @DisplayName("unhandled exceptions still fall back to generic 500 without leaking details")
    void genericExceptionStillMapsTo500() {
        ResponseEntity<GlobalExceptionHandler.ErrorResponse> response =
                handler.handleGeneric(new RuntimeException("some internal detail"));

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.INTERNAL_SERVER_ERROR);
        assertThat(response.getBody()).isNotNull();
        assertThat(response.getBody().message()).doesNotContain("some internal detail");
    }

    /** Dummy controller purely to obtain a real MethodParameter for the type-mismatch test. */
    static class DummyController {
        public void byId(java.util.UUID id) { /* no-op */ }
    }
}
