package com.example.api_gateway.filter;

import com.example.api_gateway.exception.customexception.TooManyRequestException;
import com.example.api_gateway.services.GlobalRateLimitService;
import com.example.api_gateway.util.IpUtils;
import org.springframework.cloud.gateway.filter.GatewayFilterChain;
import org.springframework.cloud.gateway.filter.GlobalFilter;
import org.springframework.core.Ordered;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ServerWebExchange;
import reactor.core.publisher.Mono;

@Component
public class GlobalRateLimitFilter implements GlobalFilter, Ordered {

    private final GlobalRateLimitService rateLimitService;

    public GlobalRateLimitFilter(GlobalRateLimitService rateLimitService) {
        this.rateLimitService = rateLimitService;
    }

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, GatewayFilterChain chain) {

        String ip = IpUtils.getClientIp(exchange);

        return rateLimitService.isBlocked(ip)
                .flatMap(blocked -> {

                    if (blocked) {
                        throw new TooManyRequestException(
                                "Too many requests. Limit is 100 per minute"
                        );
                    }

                    return chain.filter(exchange);
                });
    }

    @Override
    public int getOrder() {
        return -3;
    }
}
