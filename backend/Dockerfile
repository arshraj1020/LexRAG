# ── Build stage ───────────────────────────────────────────────
FROM eclipse-temurin:21-jdk-alpine AS builder

WORKDIR /build
COPY pom.xml .
COPY src ./src

RUN apk add --no-cache maven && \
    mvn -q -DskipTests package

# ── Runtime stage ─────────────────────────────────────────────
FROM eclipse-temurin:21-jre-alpine AS runtime

LABEL maintainer="LexRAG"
LABEL description="LexRAG — AI Legal Research Backend"

# curl is required by the docker-compose healthcheck for this service
# (CMD-SHELL "curl -sf http://localhost:8080/actuator/health") -- the
# eclipse-temurin *-jre-alpine base image does not include it by default.
RUN apk add --no-cache curl

RUN addgroup -S lexrag && adduser -S lexrag -G lexrag

WORKDIR /app

COPY --from=builder /build/target/lexrag-backend-*.jar app.jar

RUN mkdir -p /app/uploads && chown -R lexrag:lexrag /app

USER lexrag

EXPOSE 8080

ENTRYPOINT ["java", \
    "-XX:+UseContainerSupport", \
    "-XX:MaxRAMPercentage=75.0", \
    "-jar", "app.jar"]
