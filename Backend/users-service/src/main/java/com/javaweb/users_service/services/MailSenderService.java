package com.javaweb.users_service.services;

import com.javaweb.users_service.dto.MailJob;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.mail.SimpleMailMessage;
import org.springframework.mail.javamail.JavaMailSender;
import org.springframework.stereotype.Service;

@Service
@RequiredArgsConstructor
public class MailSenderService {

    private final JavaMailSender mailSender;

    @Value("${spring.mail.username}")
    private String from;

    public void send(MailJob job) {
        SimpleMailMessage message = new SimpleMailMessage();
        if (from != null && !from.isBlank()) {
            message.setFrom(from);
        }
        message.setTo(job.getTo());
        message.setSubject(job.getSubject());
        message.setText(job.getBody());
        mailSender.send(message);
    }
}
