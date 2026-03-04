package com.javaweb.users_service.repository;

import com.javaweb.users_service.entity.User;
import com.javaweb.users_service.enums.UserStatus;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface AuthRepository extends JpaRepository<User,Long> {
    boolean existsByUsername(String username);
    boolean existsByEmail(String email);
    Optional<User> findByUsernameAndStatus(String username, UserStatus status);
}
