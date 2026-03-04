package com.javaweb.users_service.repository;

import com.javaweb.users_service.entity.User;
import com.javaweb.users_service.repository.custom.UserRepositoryCustom;
import org.springframework.data.jpa.repository.JpaRepository;

public interface UserRepository extends JpaRepository<User, Long>, UserRepositoryCustom {

}
