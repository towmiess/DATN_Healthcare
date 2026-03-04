package com.javaweb.users_service.util;

import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

@Component
public class HastextUtil {
    public boolean hasText(String value) {
        return value != null && !value.trim().isEmpty();
    }
}
