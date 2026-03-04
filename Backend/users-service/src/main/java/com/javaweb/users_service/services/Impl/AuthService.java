package com.javaweb.users_service.services.Impl;

import com.javaweb.users_service.dto.request.SignUpRequest;
import com.javaweb.users_service.dto.response.BaseResponse;
import com.javaweb.users_service.entity.Role;
import com.javaweb.users_service.entity.User;
import com.javaweb.users_service.enums.UserStatus;
import com.javaweb.users_service.exception.customexception.BadRequestException;
import com.javaweb.users_service.repository.AuthRepository;
import com.javaweb.users_service.repository.RoleRepository;
import com.javaweb.users_service.services.IAuthServices;
import com.javaweb.users_service.util.ResponseUtils;
import lombok.RequiredArgsConstructor;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

@RequiredArgsConstructor
@Service
public class AuthService implements IAuthServices {

    private final AuthRepository authRepository;
    private final RoleRepository roleRepository;
    private final PasswordEncoder passwordEncoder;

    @Override
    public BaseResponse<Void> createUser(SignUpRequest signUpRequest) {
        //check password confirm
        if(!signUpRequest.getPassword().equals(signUpRequest.getConfirmPassword())){
            throw new BadRequestException("Passwords do not match!");
        }
        //check email
        if(authRepository.existsByEmail(signUpRequest.getEmail())){
            throw new BadRequestException("Email already exists!");
        }
        //check username
        if(authRepository.existsByUsername(signUpRequest.getUsername())){
            throw new BadRequestException("Username already exists!");
        }
        Role role = roleRepository.findByName("USER")
                .orElseThrow(() -> new BadRequestException("Role not found!"));
        User newUser = User.builder()
                .fullName(signUpRequest.getFullName())
                .email(signUpRequest.getEmail())
                .phoneNumber(signUpRequest.getPhoneNumber())
                .username(signUpRequest.getUsername())
                .password(passwordEncoder.encode(signUpRequest.getPassword()))
                .status(UserStatus.ACTIVE)
                .build();
        newUser.getRoles().add(role);
        authRepository.save(newUser);

        return ResponseUtils.success("Success create user!");
    }
}
