package com.javaweb.users_service.dto.request;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.*;

@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class GetAllUserRequest {
    private Long lastId;
    private String fullName;
    private String username;
    private String phoneNumber;
    private String status;
    private Long size;
}
