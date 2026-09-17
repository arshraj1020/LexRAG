package com.lexrag;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.cache.annotation.EnableCaching;
import org.springframework.scheduling.annotation.EnableAsync;

/**
 * LexRAG — AI Legal Research Intelligence Platform
 *
 * <p>Spring Boot entry point for the LexRAG backend API.
 * Handles authentication, document management, research sessions
 * and orchestration with the FastAPI AI service.
 */
@SpringBootApplication
@EnableCaching
@EnableAsync
public class LexRagApplication {

    public static void main(String[] args) {
        SpringApplication.run(LexRagApplication.class, args);
    }
}
