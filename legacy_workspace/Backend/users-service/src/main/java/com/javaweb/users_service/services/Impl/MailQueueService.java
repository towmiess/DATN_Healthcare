package com.javaweb.users_service.services.Impl;

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
                .body(buildOtpEmailHtml(otp))
                .html(true)
                .attempt(0)
                .build();
        enqueue(job);
    }

    private String buildOtpEmailHtml(String otp) {
        String safeOtp = otp == null ? "" : otp.trim();
        return """
                <!DOCTYPE html>
                <html>
                  <body style="margin:0;padding:0;background:#f4f6fb;">
                    <table role="presentation" width="100%%" cellspacing="0" cellpadding="0" style="padding:24px 0;">
                      <tr>
                        <td align="center">
                          <table role="presentation" width="520" cellspacing="0" cellpadding="0" style="background:#ffffff;border-radius:16px;box-shadow:0 6px 24px rgba(16,24,40,0.08);overflow:hidden;">
                            <tr>
                              <td style="background:#0f172a;color:#ffffff;padding:22px 28px;font-family:Arial,sans-serif;">
                                <div style="font-size:20px;font-weight:700;letter-spacing:0.6px;">Verification Code</div>
                                <div style="font-size:13px;opacity:0.85;margin-top:4px;">Use this code to continue</div>
                              </td>
                            </tr>
                            <tr>
                              <td style="padding:28px;font-family:Arial,sans-serif;color:#111827;">
                                <div style="font-size:15px;margin-bottom:12px;">Hello,</div>
                                <div style="font-size:15px;line-height:1.6;color:#374151;">
                                  Here is your one-time password (OTP). It is valid for 2 minutes.
                                </div>
                                <div style="text-align:center;margin:26px 0;">
                                  <div style="display:inline-block;color:#2563eb;font-size:40px;font-weight:800;letter-spacing:8px;">
                                    %s
                                  </div>
                                </div>
                                <div style="font-size:12px;color:#6b7280;line-height:1.6;">
                                  If you did not request this, you can ignore this email.
                                </div>
                              </td>
                            </tr>
                            <tr>
                              <td style="background:#f9fafb;color:#6b7280;padding:16px 28px;font-family:Arial,sans-serif;font-size:11px;text-align:center;">
                                This is an automated message. Please do not reply.
                              </td>
                            </tr>
                          </table>
                        </td>
                      </tr>
                    </table>
                  </body>
                </html>
                """.formatted(safeOtp);
    }
}
