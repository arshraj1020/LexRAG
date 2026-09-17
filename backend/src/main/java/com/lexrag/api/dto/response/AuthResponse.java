package com.lexrag.api.dto.response;

import com.lexrag.domain.enums.UserRole;

import java.util.UUID;

public record AuthResponse(
        String token,
        String tokenType,
        UUID userId,
        String email,
        String fullName,
        UserRole role
) {
    public static AuthResponse of(String token, UUID userId, String email, String fullName, UserRole role) {
        return new AuthResponse(token, "Bearer", userId, email, fullName, role);
    }
}
