package com.javaweb.users_service.services;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.javaweb.users_service.dto.MailJob;
import jakarta.annotation.PostConstruct;
import jakarta.annotation.PreDestroy;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;

import java.time.Duration;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

@Slf4j
@Component
@RequiredArgsConstructor
public class MailQueueWorker {
    private static final int MAX_ATTEMPTS = 3;

    private final StringRedisTemplate redisTemplate;
    private final ObjectMapper objectMapper;
    private final MailSenderService mailSenderService;

    private final ExecutorService executor = Executors.newSingleThreadExecutor(r -> {
        Thread thread = new Thread(r, "mail-queue-worker");
        thread.setDaemon(true);
        return thread;
    });

    private volatile boolean running = true;

    @PostConstruct
    public void start() {
        executor.execute(this::runLoop);
    }

    @PreDestroy
    public void stop() {
        running = false;
        executor.shutdownNow();
    }

    private void runLoop() {
        while (running) {
            try {
                String payload = redisTemplate.opsForList()
                        .rightPop(MailQueueService.MAIL_QUEUE_KEY, Duration.ofSeconds(5));
                if (payload == null) {
                    continue;
                }
                MailJob job;
                try {
                    job = objectMapper.readValue(payload, MailJob.class);
                } catch (Exception e) {
                    log.warn("Invalid mail job payload: {}", e.getMessage());
                    continue;
                }
                try {
                    mailSenderService.send(job);
                } catch (Exception e) {
                    requeue(job, e);
                }
            } catch (Exception e) {
                log.warn("Mail queue worker error: {}", e.getMessage());
            }
        }
    }

    private void requeue(MailJob job, Exception e) {
        int nextAttempt = job.getAttempt() + 1;
        if (nextAttempt <= MAX_ATTEMPTS) {
            job.setAttempt(nextAttempt);
            try {
                String payload = objectMapper.writeValueAsString(job);
                redisTemplate.opsForList().leftPush(MailQueueService.MAIL_QUEUE_KEY, payload);
            } catch (Exception ex) {
                log.warn("Failed to requeue mail job: {}", ex.getMessage());
            }
            return;
        }
        log.warn("Drop mail job after {} attempts: {}", nextAttempt - 1, e.getMessage());
    }
}
