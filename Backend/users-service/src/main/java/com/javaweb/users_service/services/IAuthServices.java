package com.javaweb.users_service.services;

import com.javaweb.users_service.dto.request.LoginRequest;
import com.javaweb.users_service.dto.request.SignUpRequest;
import com.javaweb.users_service.dto.response.BaseResponse;
import com.javaweb.users_service.dto.response.LoginResponse;

public interface IAuthServices {
    BaseResponse<Void> createUser(SignUpRequest signUpRequest);
    BaseResponse<LoginResponse> login(LoginRequest loginRequest);
}
