package com.javaweb.users_service.services;

import com.javaweb.users_service.dto.response.BaseResponse;
import com.javaweb.users_service.dto.response.UserResponse;

import java.util.List;
import java.util.Map;

public interface IUserServices {
    BaseResponse<List<UserResponse>> getAllUsers(Map<String, Object> params);
}
