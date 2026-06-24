package com.javaweb.users_service.repository.custom;

import com.javaweb.users_service.dto.request.GetAllUserRequest;

import java.util.List;

public interface UserRepositoryCustom {
    List<Object[]> findAllUsers(GetAllUserRequest request);
}
