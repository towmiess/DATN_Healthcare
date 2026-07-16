package com.javaweb.users_service.services;

import com.javaweb.users_service.dto.request.*;
import com.javaweb.users_service.dto.response.*;

import java.time.Instant;

public interface IAuthServices {
    BaseResponse<Void> createUser(SignUpRequest signUpRequest);
    BaseResponse<LoginResponse> login(LoginRequest loginRequest);
    BaseResponse<Void> logout(String accessTokenId, String refreshToken, Instant expiredAt);
    BaseResponse<Void> changePass(ChangePassRequest changePassRequest, Long userId);
    BaseResponse<CheckMailResponse> checkMail(String email);
    BaseResponse<CheckOTPResponse> checkOtp(String OTP,Long userId);
    BaseResponse<Void> resetPassword(ResetPasswordRequest resetPasswordRequest);
    BaseResponse<RefreshResponse> refreshToken(LogoutRequest refreshToken);
}
