package com.example.api_gateway.response;

import lombok.*;

import java.time.Instant;
import java.util.List;

@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class JwtPayloadResponse {
    private Long userId;
    private List<String> roles;
    private String username;
    private Instant tokenExpiredAt;
    private Instant tokenCreatedAt;
    private String tokenId;
}
