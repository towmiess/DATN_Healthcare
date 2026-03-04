package com.javaweb.users_service.services;

import com.javaweb.users_service.dto.request.SignUpRequest;
import com.javaweb.users_service.dto.response.BaseResponse;

public interface IAuthServices {
    BaseResponse<Void> createUser(SignUpRequest signUpRequest);
}
