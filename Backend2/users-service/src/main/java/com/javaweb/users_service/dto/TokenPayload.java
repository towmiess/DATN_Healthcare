package com.javaweb.users_service.dto;

import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.time.Instant;
import java.util.List;

@Getter
@Setter
@NoArgsConstructor
public class TokenPayload {
    private Long userId;
    private List<String> roles;
    private String username;
    private Instant tokenExpiredAt;
    private Instant tokenCreatedAt;
    private String tokenId;
}
