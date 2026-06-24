package com.javaweb.users_service.controller;

import com.javaweb.users_service.dto.TokenPayload;
import com.javaweb.users_service.dto.request.*;
import com.javaweb.users_service.dto.response.*;
import com.javaweb.users_service.exception.customexception.UnauthorizedException;
import com.javaweb.users_service.services.Impl.AuthService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.time.Instant;

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

    @PostMapping("/logout")
    public ResponseEntity<BaseResponse<Void>> logout(
            @Valid @RequestBody(required = false) LogoutRequest logoutRequest
    ){
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        if (auth == null || !(auth.getPrincipal() instanceof TokenPayload principal)) {
            throw new UnauthorizedException("Unauthorized!");
        }
        String accessTokenId = principal.getTokenId();
        Instant expiredAt = principal.getTokenExpiredAt();
        String refreshTokenValue = logoutRequest.getRefreshToken();

        return ResponseEntity.ok().body(authService.logout(accessTokenId, refreshTokenValue, expiredAt));
    }

    @PostMapping("/change-pass")
    public ResponseEntity<BaseResponse<Void>> changePass(@Valid @RequestBody ChangePassRequest changePassRequest){
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        if (auth == null || !(auth.getPrincipal() instanceof TokenPayload principal)) {
            throw new UnauthorizedException("Unauthorized!");
        }
        Long userId = principal.getUserId();

        return ResponseEntity.ok().body(authService.changePass(changePassRequest, userId));
    }

    @PostMapping("/check-mail")
    public ResponseEntity<BaseResponse<CheckMailResponse>> checkMail(@Valid @RequestBody CheckMailRequest checkMailRequest){
        return ResponseEntity.ok().body(authService.checkMail(checkMailRequest.getEmail()));
    }

    @PostMapping("check-otp")
    public ResponseEntity<BaseResponse<CheckOTPResponse>> checkOtp(@Valid @RequestBody CheckOtpRequest checkOtpRequest){
        return ResponseEntity.ok().body(authService.checkOtp(checkOtpRequest.getOtp(), checkOtpRequest.getUserId()));
    }

    @PostMapping("reset-password")
    public ResponseEntity<BaseResponse<Void>> resetPassword(@Valid @RequestBody ResetPasswordRequest resetPasswordRequest){

        return ResponseEntity.ok().body(authService.resetPassword(resetPasswordRequest));
    }

    @PostMapping("/refresh-token")
    public ResponseEntity<BaseResponse<RefreshResponse>> refreshToken(@Valid @RequestBody LogoutRequest refreshToken){

        return ResponseEntity.ok().body(authService.refreshToken(refreshToken));

    }
}
