package com.example.api_gateway.exception;

import com.example.api_gateway.exception.customexception.TooManyRequestException;
import com.example.api_gateway.exception.customexception.UnauthorizedException;
import com.example.api_gateway.response.BaseResponse;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import static com.example.api_gateway.util.ExceptionUtils.buildErrorResponse;

@RestControllerAdvice
public class GlobalExceptionHandler {
    @ExceptionHandler(UnauthorizedException.class)
    ResponseEntity<BaseResponse<Void>> unauthorized(UnauthorizedException ex){
        return buildErrorResponse(HttpStatus.UNAUTHORIZED,"UNAUTHORIZED", ex.getMessage());
    };

    @ExceptionHandler(TooManyRequestException.class)
    ResponseEntity<BaseResponse<Void>> unauthorized(TooManyRequestException ex){
        return buildErrorResponse(HttpStatus.TOO_MANY_REQUESTS,"TOO_MANY_REQUESTS", ex.getMessage());
    };
}
