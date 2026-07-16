package com.javaweb.users_service.util;

import com.javaweb.users_service.dto.request.GetAllUserRequest;
import com.javaweb.users_service.enums.UserStatus;
import com.javaweb.users_service.exception.customexception.BadRequestException;
import org.springframework.stereotype.Component;

import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.Locale;
import java.util.Map;

@Component
public class UserManagementUtil {
    private static final long DEFAULT_PAGE_SIZE = 20L;
    private static final long MAX_PAGE_SIZE = 100L;

    public GetAllUserRequest toListRequest(Map<String, Object> params) {
        Long requestedSize = toLong(params.get("size"));

        return GetAllUserRequest.builder()
                .lastId(toLong(params.get("lastId")))
                .fullName(trimToNull(params.get("fullName")))
                .email(trimToNull(params.get("email")))
                .phoneNumber(trimToNull(params.get("phoneNumber")))
                .status(normalizeAllowedStatus(trimToNull(params.get("status"))))
                .size(normalizeSize(requestedSize))
                .build();
    }

    public String trimToNull(Object value) {
        if (value == null) {
            return null;
        }

        String text = String.valueOf(value).trim();
        return text.isEmpty() ? null : text;
    }

    public UserStatus resolveStatus(String value) {
        String normalized = normalizeStatus(value);
        if (normalized == null) {
            throw new BadRequestException("Status is required");
        }

        try {
            UserStatus status = UserStatus.valueOf(normalized);
            if (status == UserStatus.INACTIVE) {
                throw new BadRequestException("Only ACTIVE or BLOCKED status is supported");
            }
            return status;
        } catch (IllegalArgumentException ex) {
            throw new BadRequestException("Invalid user status: " + value);
        }
    }

    public Instant recentUserStart(int days) {
        int safeDays = Math.max(days, 1);
        return Instant.now().minus(safeDays, ChronoUnit.DAYS);
    }

    private String normalizeAllowedStatus(String value) {
        String normalized = normalizeStatus(value);
        if (normalized == null) {
            return null;
        }

        return resolveStatus(normalized).name();
    }

    private String normalizeStatus(String value) {
        String trimmed = trimToNull(value);
        return trimmed == null ? null : trimmed.toUpperCase(Locale.ROOT);
    }

    private Long normalizeSize(Long size) {
        if (size == null) {
            return DEFAULT_PAGE_SIZE;
        }
        if (size <= 0) {
            return DEFAULT_PAGE_SIZE;
        }
        return Math.min(size, MAX_PAGE_SIZE);
    }

    private Long toLong(Object value) {
        if (value == null) {
            return null;
        }
        if (value instanceof Number number) {
            return number.longValue();
        }
        try {
            return Long.parseLong(String.valueOf(value).trim());
        } catch (NumberFormatException ex) {
            throw new BadRequestException("Invalid number value: " + value);
        }
    }
}
