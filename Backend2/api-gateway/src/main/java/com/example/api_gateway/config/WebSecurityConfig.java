package com.example.api_gateway.config;

import org.springframework.core.io.buffer.DataBuffer;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpMethod;
import org.springframework.security.config.annotation.web.reactive.EnableWebFluxSecurity;
import org.springframework.security.config.web.server.ServerHttpSecurity;
import org.springframework.security.web.server.SecurityWebFilterChain;
import reactor.core.publisher.Mono;

import java.nio.charset.StandardCharsets;

@Configuration
@EnableWebFluxSecurity
public class WebSecurityConfig {

    @Bean
    public SecurityWebFilterChain securityWebFilterChain(ServerHttpSecurity http) {
        return http
                .csrf(ServerHttpSecurity.CsrfSpec::disable)
                .cors(cors -> {})
                .exceptionHandling(exception -> exception
                        .authenticationEntryPoint((exchange, ex) -> writeJson(exchange, HttpStatus.UNAUTHORIZED, "Unauthorized", "Invalid or expired token"))
                        .accessDeniedHandler((exchange, ex) -> writeJson(exchange, HttpStatus.FORBIDDEN, "FORBIDDEN", "Forbidden: access denied"))
                )
                .authorizeExchange(ex -> ex
                        .pathMatchers(HttpMethod.OPTIONS, "/**").permitAll()
                        .pathMatchers(
                                "/api/auth/signup",
                                "/api/auth/signin",
                                "/api/auth/check-mail",
                                "/api/auth/check-otp",
                                "/api/auth/reset-password",
                                "/api/auth/refresh-token",
                                "/api/users/count",
                                "/api/health",
                                "/api/rag/health",
                                "/actuator/health",
                                "/actuator/health/**"
                        ).permitAll()
                        .anyExchange().authenticated()
                )
                .oauth2ResourceServer(oauth2 -> oauth2.jwt(jwt -> {}))
                .build();
    }

    private Mono<Void> writeJson(org.springframework.web.server.ServerWebExchange exchange,
                                 HttpStatus status,
                                 String code,
                                 String message) {
        exchange.getResponse().setStatusCode(status);
        exchange.getResponse().getHeaders().setContentType(MediaType.APPLICATION_JSON);
        String body = """
                {"code":"%s","message":"%s"}
                """.formatted(code, message);
        DataBuffer buffer = exchange.getResponse().bufferFactory().wrap(body.getBytes(StandardCharsets.UTF_8));
        return exchange.getResponse().writeWith(Mono.just(buffer));
    }
}
