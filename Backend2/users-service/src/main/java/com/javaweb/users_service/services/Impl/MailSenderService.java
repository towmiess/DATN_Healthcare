package com.javaweb.users_service.services.Impl;

import com.javaweb.users_service.dto.MailJob;
import jakarta.mail.MessagingException;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.mail.javamail.JavaMailSender;
import org.springframework.mail.javamail.MimeMessageHelper;
import org.springframework.stereotype.Service;

import jakarta.mail.internet.MimeMessage;

import java.io.UnsupportedEncodingException;

@Service
@RequiredArgsConstructor
public class MailSenderService {

    private final JavaMailSender mailSender;

    @Value("${spring.mail.username}")
    private String from;

    @Value("${app.mail.from-name}")
    private String fromName;

    public void send(MailJob job) throws MessagingException {
        MimeMessage message = mailSender.createMimeMessage();
        MimeMessageHelper helper = new MimeMessageHelper(message, "UTF-8");

        applyFrom(helper);
        helper.setTo(job.getTo());
        helper.setSubject(job.getSubject());
        helper.setText(job.getBody(), job.isHtml());

        mailSender.send(message);
    }

    private void applyFrom(MimeMessageHelper helper) throws MessagingException {
        if (from == null || from.isBlank()) {
            return;
        }
        if (fromName == null || fromName.isBlank()) {
            helper.setFrom(from);
            return;
        }
        try {
            helper.setFrom(from, fromName.trim());
        } catch (UnsupportedEncodingException e) {
            helper.setFrom(from);
        }
    }
}
