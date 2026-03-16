package com.javaweb.users_service.repository;

import com.javaweb.users_service.entity.UserEntity;
import com.javaweb.users_service.enums.UserStatus;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface AuthRepository extends JpaRepository<UserEntity,Long> {
    boolean existsByUsername(String username);
    boolean existsByEmail(String email);
    Optional<UserEntity> findByEmailAndDeletedFalse(String email);
    Optional<UserEntity> findByUsernameAndStatus(String username, UserStatus status);

}
