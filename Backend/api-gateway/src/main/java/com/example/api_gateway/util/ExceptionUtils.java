package com.example.api_gateway.util;

import com.example.api_gateway.response.BaseResponse;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Component;

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
}
