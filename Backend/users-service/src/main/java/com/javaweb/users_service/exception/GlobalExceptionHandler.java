package com.javaweb.users_service.exception;

import com.javaweb.users_service.dto.response.BaseResponse;
import com.javaweb.users_service.exception.customexception.BadRequestException;
import com.javaweb.users_service.exception.customexception.JwtGenerationException;
import com.javaweb.users_service.exception.customexception.UnauthorizedException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.authentication.BadCredentialsException;
import org.springframework.security.core.userdetails.UsernameNotFoundException;
import org.springframework.validation.FieldError;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.util.stream.Collectors;

import static com.javaweb.users_service.util.ExceptionUtils.buildErrorResponse;

@RestControllerAdvice
public class GlobalExceptionHandler {
    //lỗi client
    @ExceptionHandler(BadRequestException.class)
    ResponseEntity<BaseResponse<Void>> badRequestException(BadRequestException ex){
        return buildErrorResponse(HttpStatus.BAD_REQUEST,"BAD_REQUEST", ex.getMessage());
    };
    //ko có quyền truy cập
    @ExceptionHandler(UnauthorizedException.class)
    ResponseEntity<BaseResponse<Void>> unauthorized(UnauthorizedException ex){
        return buildErrorResponse(HttpStatus.UNAUTHORIZED,"UNAUTHORIZED", ex.getMessage());
    };
    //sai mật khẩu
    @ExceptionHandler(BadCredentialsException.class)
    ResponseEntity<BaseResponse<Void>> handleBadCredentialsException(BadCredentialsException ex){
        return buildErrorResponse(HttpStatus.BAD_REQUEST,"BAD_REQUEST","Username or password is incorrect!"
        );
    }
    //tài khoản ko tồn tại
    @ExceptionHandler(UsernameNotFoundException.class)
    ResponseEntity<BaseResponse<Void>> handleUsernameNotFoundException(UsernameNotFoundException ex){
        return buildErrorResponse(HttpStatus.BAD_REQUEST,"USER_NOT_FOUND","User does not exist!"
        );
    }
    @ExceptionHandler(JwtGenerationException.class)
    ResponseEntity<BaseResponse<Void>> invalidParamException(JwtGenerationException ex){
        return buildErrorResponse(HttpStatus.INTERNAL_SERVER_ERROR,"JWT_NOT_CREATE", ex.getMessage());
    };
    //lỗi thiếu dữ liệu gửi lên
    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<BaseResponse<Void>> handleValidation(
            MethodArgumentNotValidException ex) {

        String error = ex.getBindingResult()
                .getFieldErrors()
                .stream()
                .map(FieldError::getDefaultMessage)
                .collect(Collectors.joining(", "));

        return buildErrorResponse(HttpStatus.BAD_REQUEST,"BAD_REQUEST", error);
    };
}
