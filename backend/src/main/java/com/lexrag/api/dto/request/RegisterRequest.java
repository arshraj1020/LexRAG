package com.lexrag.api.dto.request;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record RegisterRequest(
        @NotBlank @Email(message = "Valid email required")
        String email,

        @NotBlank @Size(min = 2, max = 100, message = "Full name must be 2-100 characters")
        String fullName,

        @NotBlank @Size(min = 8, max = 128, message = "Password must be 8-128 characters")
        String password
) {}
