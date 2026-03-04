package com.javaweb.users_service.mapper;

import com.javaweb.users_service.dto.request.GetAllUserRequest;
import com.javaweb.users_service.dto.response.UserResponse;
import com.javaweb.users_service.enums.UserStatus;
import org.springframework.stereotype.Component;

import java.util.Map;

@Component
public class UserMapper {

    private Long toLong(Object value) {
        if (value == null) return null;

        if (value instanceof Number) {
            return ((Number) value).longValue();
        }

        if (value instanceof String) {
            return Long.parseLong((String) value);
        }

        throw new IllegalArgumentException("Cannot convert to Long: " + value);
    }
    public GetAllUserRequest toRequest(Map<String, Object> params) {
        return GetAllUserRequest.builder()
                .lastId(toLong(params.get("lastId")))
                .fullName((String)params.get("fullName"))
                .username((String)params.get("username"))
                .phoneNumber((String)params.get("phoneNumber"))
                .status((String)params.get("status"))
                .size(toLong(params.get("size")))
                .build();
    }

    public UserResponse toResponse(Object[] row){
        return UserResponse.builder()
                .id(((Number) row[0]).longValue())
                .fullName((String)row[1])
                .email((String)row[2])
                .phoneNumber((String)row[3])
                .username((String)row[4])
                .avatar((String)row[5])
                .status((String)row[6])
                .build();
    }
}
