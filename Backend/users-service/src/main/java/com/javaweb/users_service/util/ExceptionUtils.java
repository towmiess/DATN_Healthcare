package com.javaweb.users_service.util;

import com.javaweb.users_service.dto.response.BaseResponse;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Component;

import java.io.IOException;

@Component
public class ExceptionUtils {

    public static ResponseEntity<BaseResponse<Void>> buildErrorResponse(HttpStatus status, String code, String message){
        return ResponseEntity.status(status).body(
                BaseResponse.<Void>builder()
                        .code(code)
                        .message(message)
                        .build()
        );
    };

    public static void sendUnauthorized(HttpServletResponse response, String message)
            throws IOException {

        response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
        response.setContentType("application/json");
        response.setCharacterEncoding("UTF-8");

        response.getWriter().write("""
        {
          "code": "401",
          "message": "%s"
        }
        """.formatted(message));
    };
}