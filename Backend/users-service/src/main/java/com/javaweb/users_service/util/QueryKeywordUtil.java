package com.javaweb.users_service.util;

import com.javaweb.users_service.dto.request.GetAllUserRequest;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.List;

@Component
@RequiredArgsConstructor
public class QueryKeywordUtil {

    private final HastextUtil hastextUtil;

    public String buildKeywordCondition(GetAllUserRequest request) {

        List<String> conditions = new ArrayList<>();

        if (hastextUtil.hasText(request.getEmail())) {
            conditions.add("LOWER(u.username) LIKE LOWER(:username)");
        }

        if (hastextUtil.hasText(request.getPhoneNumber())) {
            conditions.add("LOWER(u.phone_number) LIKE LOWER(:phoneNumber)");
        }

        if (hastextUtil.hasText(request.getFullName())) {
            conditions.add("LOWER(u.full_name) LIKE LOWER(:fullName)");
        }

        return String.join(" OR ", conditions);
    }
}
