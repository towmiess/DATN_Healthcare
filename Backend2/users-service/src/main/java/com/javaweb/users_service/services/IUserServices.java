package com.javaweb.users_service.services;

import com.javaweb.users_service.dto.request.UpdateUserRequest;
import com.javaweb.users_service.dto.request.UpdateUserStatusRequest;
import com.javaweb.users_service.dto.response.BaseResponse;
import com.javaweb.users_service.dto.response.UserManagementSummaryResponse;
import com.javaweb.users_service.dto.response.UserResponse;

import java.util.List;
import java.util.Map;

public interface IUserServices {
    BaseResponse<List<UserResponse>> getAllUsers(Map<String, Object> params);

    BaseResponse<UserResponse> getUserById(Long id);

    BaseResponse<UserResponse> updateUser(Long id, UpdateUserRequest request);

    BaseResponse<UserResponse> updateUserStatus(Long id, UpdateUserStatusRequest request);

    BaseResponse<Void> deleteUser(Long id);

    BaseResponse<UserManagementSummaryResponse> getSummary();
}
