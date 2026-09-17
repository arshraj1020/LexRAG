package com.lexrag;

import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;

/**
 * Smoke test — verifies the Spring context loads without errors.
 *
 * Requires a running PostgreSQL + Redis (use Testcontainers for CI).
 * Mark @Disabled to skip in environments without Docker.
 */
@SpringBootTest
@ActiveProfiles("test")
class LexRagApplicationTests {

    @Test
    void contextLoads() {
        // If the Spring context starts without throwing, this passes.
    }
}
