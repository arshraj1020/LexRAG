package com.lexrag.service.interfaces;

import com.lexrag.api.dto.request.LoginRequest;
import com.lexrag.api.dto.request.RegisterRequest;
import com.lexrag.api.dto.response.AuthResponse;

public interface AuthService {
    AuthResponse register(RegisterRequest request);
    AuthResponse login(LoginRequest request);
}
