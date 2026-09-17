package com.lexrag.security.jwt;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.userdetails.User;
import org.springframework.security.core.userdetails.UserDetails;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class JwtTokenProviderTest {

    // 64-char secret for HS512
    private static final String TEST_SECRET =
            "this-is-a-test-secret-that-is-at-least-64-characters-long-for-hs512!!";
    private static final long EXPIRATION_MS = 3_600_000L; // 1 hour

    private JwtTokenProvider tokenProvider;

    @BeforeEach
    void setUp() {
        tokenProvider = new JwtTokenProvider(TEST_SECRET, EXPIRATION_MS);
    }

    @Test
    void generateToken_thenValidateAndExtractUsername() {
        UserDetails userDetails = new User(
                "test@lexrag.com", "irrelevant",
                List.of(new SimpleGrantedAuthority("ROLE_USER")));

        Authentication auth = new UsernamePasswordAuthenticationToken(
                userDetails, null, userDetails.getAuthorities());

        String token = tokenProvider.generateToken(auth);

        assertThat(token).isNotBlank();
        assertThat(tokenProvider.validateToken(token)).isTrue();
        assertThat(tokenProvider.getUsernameFromToken(token)).isEqualTo("test@lexrag.com");
    }

    @Test
    void invalidToken_returnsFalse() {
        assertThat(tokenProvider.validateToken("not.a.jwt")).isFalse();
    }

    @Test
    void tamperedToken_returnsFalse() {
        UserDetails userDetails = new User(
                "a@b.com", "pass",
                List.of(new SimpleGrantedAuthority("ROLE_USER")));
        Authentication auth = new UsernamePasswordAuthenticationToken(
                userDetails, null, userDetails.getAuthorities());

        String token = tokenProvider.generateToken(auth);
        String tampered = token.substring(0, token.length() - 4) + "XXXX";

        assertThat(tokenProvider.validateToken(tampered)).isFalse();
    }
}
