package com.javaweb.users_service.mapper;

import com.javaweb.users_service.dto.request.GetAllUserRequest;
import com.javaweb.users_service.entity.RoleEntity;
import com.javaweb.users_service.entity.UserEntity;
import com.javaweb.users_service.dto.response.UserResponse;
import org.springframework.stereotype.Component;

import java.sql.Timestamp;
import java.time.Instant;
import java.util.Arrays;
import java.util.List;
import java.util.Map;
import java.util.Objects;

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
                .avatar((String)row[4])
                .status((String)row[5])
                .roles(splitRoles((String) row[6]))
                .createdAt(toInstant(row[7]))
                .updatedAt(toInstant(row[8]))
                .build();
    }

    public UserResponse toResponse(UserEntity user) {
        return UserResponse.builder()
                .id(user.getId())
                .fullName(user.getFullName())
                .email(user.getEmail())
                .phoneNumber(user.getPhoneNumber())
                .avatar(user.getAvatar())
                .status(user.getStatus() == null ? null : user.getStatus().name())
                .roles(user.getRoleEntities().stream()
                        .map(RoleEntity::getName)
                        .filter(Objects::nonNull)
                        .toList())
                .createdAt(user.getCreatedAt())
                .updatedAt(user.getUpdatedAt())
                .build();
    }

    public List<String> toRoles(List<String> roles) {
        if (roles == null) {
            return List.of();
        }
        return roles;
    }

    private List<String> splitRoles(String roles) {
        if (roles == null || roles.isBlank()) {
            return List.of();
        }
        return Arrays.stream(roles.split(","))
                .map(String::trim)
                .filter(role -> !role.isEmpty())
                .toList();
    }

    private Instant toInstant(Object value) {
        if (value == null) {
            return null;
        }
        if (value instanceof Instant instant) {
            return instant;
        }
        if (value instanceof Timestamp timestamp) {
            return timestamp.toInstant();
        }
        return Instant.parse(String.valueOf(value));
    }
}
