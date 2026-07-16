package com.javaweb.users_service.dto.response;

import lombok.*;

import java.time.Instant;
import java.util.List;

@Getter
@Setter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class UserResponse {
    private Long id;
    private String fullName;
    private String email;
    private String phoneNumber;
    private String avatar;
    private String status;
    private List<String> roles;
    private Instant createdAt;
    private Instant updatedAt;
}
