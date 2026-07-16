package com.javaweb.users_service.util;

import com.javaweb.users_service.dto.response.BaseResponse;
import org.springframework.stereotype.Component;

import java.util.List;

@Component
public class ResponseUtils {

    public static <T> BaseResponse<T> success(T data) {
        return BaseResponse.<T>builder()
                .code("200")
                .message("Success")
                .data(data)
                .build();
    }

    public static <T> BaseResponse<T> success(String message, T data) {
        return BaseResponse.<T>builder()
                .code("200")
                .message(message)
                .data(data)
                .build();
    }

    

    public static BaseResponse<Void> success(String message) {
        return BaseResponse.<Void>builder()
                .code("200")
                .message(message)
                .data(null)
                .build();
    }
}
