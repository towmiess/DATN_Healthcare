package com.javaweb.users_service.services.Impl;

import com.javaweb.users_service.dto.request.GetAllUserRequest;
import com.javaweb.users_service.dto.response.BaseResponse;
import com.javaweb.users_service.dto.response.UserResponse;
import com.javaweb.users_service.mapper.UserMapper;
import com.javaweb.users_service.repository.UserRepository;
import com.javaweb.users_service.services.IUserServices;
import com.javaweb.users_service.util.ResponseUtils;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;

@Service
@RequiredArgsConstructor
public class UserService implements IUserServices {

    private final UserMapper userMapper;
    private final UserRepository userRepository;

    @Override
    public BaseResponse<List<UserResponse>> getAllUsers(Map<String, Object> params) {
        GetAllUserRequest request = userMapper.toRequest(params);
        List<Object[]> users = userRepository.findAllUsers(request);
        List<UserResponse> userResponses =users.stream()
                .map(userMapper::toResponse)
                .toList();
        return ResponseUtils.success("Successfully get all users!", userResponses);
    }
}
