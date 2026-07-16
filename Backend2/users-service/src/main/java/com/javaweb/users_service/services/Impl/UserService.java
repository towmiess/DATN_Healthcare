package com.javaweb.users_service.services.Impl;

import com.javaweb.users_service.dto.request.GetAllUserRequest;
import com.javaweb.users_service.dto.request.UpdateUserRequest;
import com.javaweb.users_service.dto.request.UpdateUserStatusRequest;
import com.javaweb.users_service.dto.response.BaseResponse;
import com.javaweb.users_service.dto.response.UserManagementSummaryResponse;
import com.javaweb.users_service.dto.response.UserResponse;
import com.javaweb.users_service.entity.UserEntity;
import com.javaweb.users_service.enums.UserStatus;
import com.javaweb.users_service.exception.customexception.BadRequestException;
import com.javaweb.users_service.mapper.UserMapper;
import com.javaweb.users_service.repository.UserRepository;
import com.javaweb.users_service.services.IUserServices;
import com.javaweb.users_service.util.UserManagementUtil;
import com.javaweb.users_service.util.ResponseUtils;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Map;

@Service
@RequiredArgsConstructor
public class UserService implements IUserServices {

    private static final int RECENT_USER_DAYS = 3;

    private final UserMapper userMapper;
    private final UserRepository userRepository;
    private final UserManagementUtil userManagementUtil;

    @Override
    @Transactional(readOnly = true)
    public BaseResponse<List<UserResponse>> getAllUsers(Map<String, Object> params) {
        GetAllUserRequest request = userManagementUtil.toListRequest(params);
        List<Object[]> users = userRepository.findAllUsers(request);
        List<UserResponse> userResponses =users.stream()
                .map(userMapper::toResponse)
                .toList();
        return ResponseUtils.success("Successfully get all users!", userResponses);
    }

    @Override
    @Transactional(readOnly = true)
    public BaseResponse<UserResponse> getUserById(Long id) {
        UserEntity user = findActiveUser(id);
        return ResponseUtils.success("Successfully get user!", userMapper.toResponse(user));
    }

    @Override
    @Transactional
    public BaseResponse<UserResponse> updateUser(Long id, UpdateUserRequest request) {
        UserEntity user = findActiveUser(id);

        String fullName = userManagementUtil.trimToNull(request.getFullName());
        if (fullName != null) {
            user.setFullName(fullName);
        }

        String phoneNumber = userManagementUtil.trimToNull(request.getPhoneNumber());
        if (phoneNumber != null) {
            user.setPhoneNumber(phoneNumber);
        }

        String avatar = userManagementUtil.trimToNull(request.getAvatar());
        if (avatar != null) {
            user.setAvatar(avatar);
        }

        String status = userManagementUtil.trimToNull(request.getStatus());
        if (status != null) {
            user.setStatus(userManagementUtil.resolveStatus(status));
        }

        UserEntity savedUser = userRepository.save(user);
        return ResponseUtils.success("Successfully update user!", userMapper.toResponse(savedUser));
    }

    @Override
    @Transactional
    public BaseResponse<UserResponse> updateUserStatus(Long id, UpdateUserStatusRequest request) {
        UserEntity user = findActiveUser(id);
        UserStatus status = userManagementUtil.resolveStatus(request.getStatus());
        user.setStatus(status);

        UserEntity savedUser = userRepository.save(user);
        return ResponseUtils.success("Successfully update user status!", userMapper.toResponse(savedUser));
    }

    @Override
    @Transactional
    public BaseResponse<Void> deleteUser(Long id) {
        UserEntity user = findActiveUser(id);
        user.setDeleted(true);
        user.setStatus(UserStatus.BLOCKED);
        userRepository.save(user);

        return ResponseUtils.success("Successfully delete user!");
    }

    @Override
    @Transactional(readOnly = true)
    public BaseResponse<UserManagementSummaryResponse> getSummary() {
        UserManagementSummaryResponse summary = UserManagementSummaryResponse.builder()
                .totalUsers(userRepository.countByDeletedFalse())
                .activeUsers(userRepository.countByStatusAndDeletedFalse(UserStatus.ACTIVE))
                .blockedUsers(userRepository.countByStatusAndDeletedFalse(UserStatus.BLOCKED))
                .recentUsers(userRepository.countRecentUsers(userManagementUtil.recentUserStart(RECENT_USER_DAYS)))
                .build();

        return ResponseUtils.success("Successfully get user summary!", summary);
    }

    private UserEntity findActiveUser(Long id) {
        return userRepository.findByIdAndDeletedFalse(id)
                .orElseThrow(() -> new BadRequestException("User not found!"));
    }
}
