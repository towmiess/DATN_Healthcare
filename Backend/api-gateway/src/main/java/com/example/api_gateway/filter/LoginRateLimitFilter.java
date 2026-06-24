package com.example.api_gateway.filter;

import com.example.api_gateway.exception.customexception.TooManyRequestException;
import com.example.api_gateway.services.LoginRateLimitService;
import com.example.api_gateway.util.IpUtils;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.cloud.gateway.filter.GatewayFilterChain;
import org.springframework.cloud.gateway.filter.GlobalFilter;
import org.springframework.core.Ordered;
import org.springframework.core.io.buffer.DataBuffer;
import org.springframework.core.io.buffer.DataBufferUtils;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.server.reactive.ServerHttpRequest;
import org.springframework.http.server.reactive.ServerHttpRequestDecorator;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ServerWebExchange;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

import java.nio.charset.StandardCharsets;

@Component
@RequiredArgsConstructor
public class LoginRateLimitFilter implements GlobalFilter, Ordered {

    private final LoginRateLimitService rateLimitService;
    private final ObjectMapper objectMapper;

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, GatewayFilterChain chain) {

        String path = exchange.getRequest().getURI().getPath();
        HttpMethod method = exchange.getRequest().getMethod();

        if (!"/api/auth/signin".equals(path) || method != HttpMethod.POST) {
            return chain.filter(exchange);
        }

        String ip = IpUtils.getClientIp(exchange);

        return DataBufferUtils.join(exchange.getRequest().getBody())
                .switchIfEmpty(Mono.defer(() -> Mono.just(exchange.getResponse().bufferFactory().wrap(new byte[0]))))
                .flatMap(dataBuffer -> {
                    byte[] bytes = new byte[dataBuffer.readableByteCount()];
                    dataBuffer.read(bytes);
                    DataBufferUtils.release(dataBuffer);

                    String body = new String(bytes, StandardCharsets.UTF_8);
                    String username = extractUsername(body);
                    if (username == null || username.isBlank()) {
                        username = "unknown";
                    }

                    Flux<DataBuffer> cachedBody = Flux.defer(() ->
                            Mono.just(exchange.getResponse().bufferFactory().wrap(bytes))
                    );

                    ServerHttpRequest mutatedRequest = new ServerHttpRequestDecorator(exchange.getRequest()) {
                        @Override
                        public Flux<DataBuffer> getBody() {
                            return cachedBody;
                        }

                        @Override
                        public HttpHeaders getHeaders() {
                            HttpHeaders headers = new HttpHeaders();
                            headers.putAll(super.getHeaders());
                            headers.remove(HttpHeaders.CONTENT_LENGTH);
                            headers.setContentLength(bytes.length);
                            return headers;
                        }
                    };

                    return rateLimitService.isBlocked(username, ip)
                            .flatMap(blocked -> {

                                if (blocked) {
                                    throw new TooManyRequestException("Too many login attempts. Try again after 60 seconds");
                                }

                                return chain.filter(
                                        exchange.mutate()
                                                .request(mutatedRequest)
                                                .build()
                                );
                            });
                });
    }

    @Override
    public int getOrder() {
        return -2;
    }

    private String extractUsername(String body) {
        if (body == null || body.isBlank()) {
            return null;
        }
        try {
            JsonNode node = objectMapper.readTree(body);
            return node.path("username").asText(null);
        } catch (Exception e) {
            return null;
        }
    }
}
