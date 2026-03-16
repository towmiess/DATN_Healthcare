package com.javaweb.users_service.mapper;

import com.javaweb.users_service.dto.request.GetAllUserRequest;
import com.javaweb.users_service.dto.response.UserResponse;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.Map;

@Component
public class UserMapper {

    private Long toLong(Object value) {
        return switch (value) {
            case null -> null;
            case Number number -> number.longValue();
            case String s -> Long.parseLong(s);
            default -> throw new IllegalArgumentException("Cannot convert to Long: " + value);
        };

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

    public List<String> toRoles(List<String> roles) {
        if (roles == null) {
            return List.of();
        }
        return roles;
    }
}
