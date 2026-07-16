package com.javaweb.users_service.dto.response;

import lombok.*;

@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class CheckOTPResponse {
    private String token;
    private Long userId;
}
