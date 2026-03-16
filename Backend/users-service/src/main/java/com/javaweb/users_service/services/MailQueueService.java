package com.javaweb.users_service.services;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.javaweb.users_service.dto.MailJob;
import lombok.RequiredArgsConstructor;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;

@Service
@RequiredArgsConstructor
public class MailQueueService {
    public static final String MAIL_QUEUE_KEY = "mail:queue";

    private final StringRedisTemplate redisTemplate;
    private final ObjectMapper objectMapper;

    public void enqueue(MailJob job) {
        try {
            String payload = objectMapper.writeValueAsString(job);
            redisTemplate.opsForList().leftPush(MAIL_QUEUE_KEY, payload);
        } catch (Exception e) {
            throw new IllegalStateException("Cannot enqueue mail job", e);
        }
    }

    public void enqueueOtpMail(String to, String otp) {
        MailJob job = MailJob.builder()
                .to(to)
                .subject("Your OTP Code")
                .body("Your OTP is: " + otp + " (valid for 60 seconds)")
                .attempt(0)
                .build();
        enqueue(job);
    }
}
