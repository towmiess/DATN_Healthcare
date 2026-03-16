package com.example.api_gateway.services;

import org.springframework.data.redis.core.ReactiveRedisTemplate;
import org.springframework.stereotype.Service;
import reactor.core.publisher.Mono;

import java.time.Duration;

@Service
public class GlobalRateLimitService {

    private final ReactiveRedisTemplate<String, String> redisTemplate;

    private static final int MAX_REQUEST = 100;
    private static final int TTL = 60;

    public GlobalRateLimitService(ReactiveRedisTemplate<String, String> redisTemplate) {
        this.redisTemplate = redisTemplate;
    }

    public Mono<Boolean> isBlocked(String ip) {

        String key = "rate_limit:" + ip;

        return redisTemplate.opsForValue()
                .increment(key)
                .flatMap(count -> {

                    if (count == 1) {
                        return redisTemplate.expire(key, Duration.ofSeconds(TTL))
                                .thenReturn(count);
                    }

                    return Mono.just(count);
                })
                .map(count -> count > MAX_REQUEST);
    }
}
