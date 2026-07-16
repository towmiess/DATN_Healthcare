package com.example.api_gateway.services;

import org.springframework.data.redis.core.ReactiveRedisTemplate;
import org.springframework.data.redis.core.script.RedisScript;
import org.springframework.stereotype.Service;
import reactor.core.publisher.Mono;

import java.util.Collections;

@Service
public class LoginRateLimitService {

    private final ReactiveRedisTemplate<String, String> redisTemplate;
    private final RedisScript<Long> script;

    private static final int MAX_ATTEMPT = 5;
    private static final int TTL = 60;

    public LoginRateLimitService(
            ReactiveRedisTemplate<String, String> redisTemplate,
            RedisScript<Long> script) {

        this.redisTemplate = redisTemplate;
        this.script = script;
    }

    public Mono<Boolean> isBlocked(String email, String ip) {

        String key = "login:attempt:" + email + ":" + ip;

        return redisTemplate.execute(
                        script,
                        Collections.singletonList(key),
                        String.valueOf(MAX_ATTEMPT),
                        String.valueOf(TTL)
                )
                .next()
                .map(result -> result == -1);
    }
}
