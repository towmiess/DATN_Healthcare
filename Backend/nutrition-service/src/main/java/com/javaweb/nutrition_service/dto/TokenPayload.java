package com.javaweb.nutrition_service.dto;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.time.Instant;
import java.util.List;

@Getter
@Setter
@NoArgsConstructor
@JsonIgnoreProperties(ignoreUnknown = true)
public class TokenPayload {
    private Long userId;
    private List<String> roles;
    private String username;
    private Instant tokenExpiredAt;
    private Instant tokenCreatedAt;
    private String tokenId;
}
