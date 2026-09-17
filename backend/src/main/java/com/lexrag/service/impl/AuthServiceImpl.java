package com.lexrag.service.impl;

import com.lexrag.api.dto.request.LoginRequest;
import com.lexrag.api.dto.request.RegisterRequest;
import com.lexrag.api.dto.response.AuthResponse;
import com.lexrag.domain.entities.User;
import com.lexrag.domain.repositories.UserRepository;
import com.lexrag.exception.ConflictException;
import com.lexrag.security.jwt.JwtTokenProvider;
import com.lexrag.service.interfaces.AuthService;
import lombok.RequiredArgsConstructor;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
public class AuthServiceImpl implements AuthService {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private final AuthenticationManager authenticationManager;
    private final JwtTokenProvider jwtTokenProvider;

    @Override
    @Transactional
    public AuthResponse register(RegisterRequest request) {
        if (userRepository.existsByEmail(request.email())) {
            throw new ConflictException("Email already registered");
        }

        User user = User.builder()
                .email(request.email())
                .fullName(request.fullName())
                .passwordHash(passwordEncoder.encode(request.password()))
                .build();

        user = userRepository.save(user);

        Authentication auth = authenticationManager.authenticate(
                new UsernamePasswordAuthenticationToken(request.email(), request.password())
        );

        String token = jwtTokenProvider.generateToken(auth);
        return AuthResponse.of(token, user.getId(), user.getEmail(), user.getFullName(), user.getRole());
    }

    @Override
    public AuthResponse login(LoginRequest request) {
        Authentication auth = authenticationManager.authenticate(
                new UsernamePasswordAuthenticationToken(request.email(), request.password())
        );

        User user = userRepository.findByEmail(request.email())
                .orElseThrow(() -> new RuntimeException("User not found after authentication"));

        String token = jwtTokenProvider.generateToken(auth);
        return AuthResponse.of(token, user.getId(), user.getEmail(), user.getFullName(), user.getRole());
    }
}
