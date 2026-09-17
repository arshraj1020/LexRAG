package com.lexrag.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.web.reactive.function.client.WebClient;

import java.time.Duration;

/**
 * WebClient configuration for backend → AI service communication.
 *
 * Uses a single shared WebClient instance with a default base URL and
 * the internal API key pre-wired into every request.
 */
@Configuration
public class WebClientConfig {

    @Value("${ai.service.url}")
    private String aiServiceUrl;

    @Value("${ai.service.internal-api-key}")
    private String internalApiKey;

    @Bean("aiServiceWebClient")
    public WebClient aiServiceWebClient() {
        return WebClient.builder()
                .baseUrl(aiServiceUrl)
                .defaultHeader(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
                .defaultHeader("X-Internal-Api-Key", internalApiKey)
                // 5-minute timeout — LLM generation can be slow on smaller hardware
                .codecs(c -> c.defaultCodecs().maxInMemorySize(2 * 1024 * 1024))
                .build();
    }
}
