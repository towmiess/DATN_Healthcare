package com.javaweb.users_service.controller;

import com.javaweb.users_service.dto.request.LoginRequest;
import com.javaweb.users_service.dto.request.SignUpRequest;
import com.javaweb.users_service.dto.response.BaseResponse;
import com.javaweb.users_service.dto.response.LoginResponse;
import com.javaweb.users_service.services.Impl.AuthService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RequiredArgsConstructor
@RestController
@RequestMapping("/api/auth")
public class AuthController {

    private final AuthService authService;

    @PostMapping("/signup")
    public ResponseEntity<BaseResponse<Void>> signup(@Valid @RequestBody SignUpRequest signUpRequest){
        return ResponseEntity.ok().body(authService.createUser(signUpRequest));
    }

    @PostMapping("/signin")
    public ResponseEntity<BaseResponse<LoginResponse>> signin(@Valid @RequestBody LoginRequest loginRequest){
        return ResponseEntity.ok().body(authService.login(loginRequest));
    }
}
