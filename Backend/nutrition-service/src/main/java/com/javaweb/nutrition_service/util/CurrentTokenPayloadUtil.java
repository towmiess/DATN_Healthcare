package com.javaweb.nutrition_service.util;

import com.javaweb.nutrition_service.dto.TokenPayload;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ResponseStatusException;

@Component
public class CurrentTokenPayloadUtil {

    public TokenPayload getCurrentTokenPayload() {
        Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
        if (authentication == null || !(authentication.getPrincipal() instanceof TokenPayload tokenPayload)) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Missing authenticated user");
        }
        if (tokenPayload.getUserId() == null) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Missing user id");
        }
        return tokenPayload;
    }
}
