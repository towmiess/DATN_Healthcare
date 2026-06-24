package com.example.api_gateway.filter;

import com.example.api_gateway.response.JwtPayloadResponse;
import com.example.api_gateway.util.SignPayloadUtil;
import com.example.api_gateway.util.UnauthorizeException;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.validation.constraints.NotNull;
import lombok.RequiredArgsConstructor;
import org.springframework.cloud.gateway.filter.GatewayFilterChain;
import org.springframework.cloud.gateway.filter.GlobalFilter;
import org.springframework.core.Ordered;
import org.springframework.core.io.buffer.DataBuffer;
import org.springframework.data.redis.core.ReactiveStringRedisTemplate;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.server.reactive.ServerHttpRequest;
import org.springframework.security.core.Authentication;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ServerWebExchange;
import reactor.core.publisher.Mono;

import java.nio.charset.StandardCharsets;
import java.util.Base64;

@Component
@RequiredArgsConstructor
public class JwtTokenFilter implements GlobalFilter, Ordered {

    private final ObjectMapper objectMapper;
    private final SignPayloadUtil  signPayloadUtil;
    private final ReactiveStringRedisTemplate redisTemplate;
    private final UnauthorizeException unauthorizeException;

    @Override
    public Mono<Void> filter(@NotNull ServerWebExchange exchange, @NotNull GatewayFilterChain chain) {

        return exchange.getPrincipal()
                .ofType(Authentication.class)
                .map(Authentication::getPrincipal)
                .ofType(Jwt.class)
                .flatMap(jwt ->
                    redisTemplate.hasKey("blacklist:access:" + jwt.getId())
                            .flatMap(blacklisted -> {
                                if(Boolean.TRUE.equals(blacklisted)) {
                                    return unauthorizeException.unauthorized(exchange, "Token revoked!");
                                }
                                Long userId = jwt.getClaim("user_id");
                                if(userId == null || jwt.getIssuedAt() == null) {
                                    return unauthorizeException.unauthorized(exchange, "Invalid token");
                                }
                                return redisTemplate.opsForValue()
                                        .get("changeAt:" + userId)
                                        .map(Long::parseLong)
                                        .defaultIfEmpty(0L)
                                        .flatMap(changeAtMs -> {
                                            long issuedAtMs = jwt.getIssuedAt().toEpochMilli();
                                            if(issuedAtMs <= changeAtMs) {
                                                return unauthorizeException.unauthorized(exchange, "Token expired!");
                                            }
                                            return forwardWithContext(exchange, chain, jwt);
                                        });
                            })
                )
                .switchIfEmpty(forwardWithContext(exchange, chain, null));
    }

    private Mono<Void> forwardWithContext(
            ServerWebExchange exchange,
            GatewayFilterChain chain,
            Jwt jwt
    ) {
        String encodedPayload = "";
        if (jwt != null) {
            try {
                JwtPayloadResponse payload = JwtPayloadResponse.builder()
                        .userId(jwt.getClaim("user_id"))
                        .roles(jwt.getClaim("roles"))
                        .username(jwt.getSubject())
                        .tokenExpiredAt(jwt.getExpiresAt())
                        .tokenCreatedAt(jwt.getIssuedAt())
                        .tokenId(jwt.getId())
                        .build();
                String json = objectMapper.writeValueAsString(payload);
                encodedPayload = Base64.getEncoder().encodeToString(json.getBytes(StandardCharsets.UTF_8));
            } catch (Exception e) {
                encodedPayload = "";
            }
        }

        String signature = signPayloadUtil.sign(encodedPayload);

        String finalEncodedPayload = encodedPayload;
        ServerHttpRequest mutatedRequest = exchange.getRequest()
                .mutate()
                .headers(headers -> {
                    headers.remove("X-User-Context");
                    headers.remove("X-User-Context-Signature");
                    headers.set("X-User-Context", finalEncodedPayload);
                    headers.set("X-User-Context-Signature", signature);
                })
                .build();

        return chain.filter(
                exchange.mutate()
                        .request(mutatedRequest)
                        .build()
        );
    }

    @Override
    public int getOrder() {
        return -1;
    }
}
