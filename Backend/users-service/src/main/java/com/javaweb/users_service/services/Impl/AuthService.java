package com.javaweb.users_service.services.Impl;

import com.javaweb.users_service.dto.request.LoginRequest;
import com.javaweb.users_service.dto.request.SignUpRequest;
import com.javaweb.users_service.dto.response.BaseResponse;
import com.javaweb.users_service.dto.response.LoginResponse;
import com.javaweb.users_service.entity.RoleEntity;
import com.javaweb.users_service.entity.UserEntity;
import com.javaweb.users_service.enums.UserStatus;
import com.javaweb.users_service.exception.customexception.BadRequestException;
import com.javaweb.users_service.repository.AuthRepository;
import com.javaweb.users_service.repository.RoleRepository;
import com.javaweb.users_service.services.IAuthServices;
import com.javaweb.users_service.util.JwtTokenUtil;
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
    private final JwtTokenUtil jwtTokenUtil;

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
        RoleEntity roleEntity = roleRepository.findByName("USER")
                .orElseThrow(() -> new BadRequestException("Role not found!"));
        UserEntity newUser = UserEntity.builder()
                .fullName(signUpRequest.getFullName())
                .email(signUpRequest.getEmail())
                .phoneNumber(signUpRequest.getPhoneNumber())
                .username(signUpRequest.getUsername())
                .password(passwordEncoder.encode(signUpRequest.getPassword()))
                .status(UserStatus.ACTIVE)
                .deleted(false)
                .build();
        newUser.getRoleEntities().add(roleEntity);
        authRepository.save(newUser);

        return ResponseUtils.success("Success create user!");
    }

    @Override
    public BaseResponse<LoginResponse> login(LoginRequest loginRequest) {
        UserEntity user = authRepository.findByUsernameAndDeletedFalse(loginRequest.getUsername())
                .orElseThrow(() -> new BadRequestException("Username not found!"));
        if(!passwordEncoder.matches(loginRequest.getPassword(), user.getPassword())){
            throw new BadRequestException("Passwords do not match!");
        }
        String accessToken = jwtTokenUtil.generateAccessToken(user);
        String refreshToken = jwtTokenUtil.generateRefreshToken(user);
        LoginResponse loginResponse = LoginResponse.builder()
                .accessToken(accessToken)
                .refreshToken(refreshToken)
                .build();
        return ResponseUtils.success("Login success full!", loginResponse);
    }

}
