package com.javaweb.users_service.services.Impl;

import com.javaweb.users_service.dto.request.*;
import com.javaweb.users_service.dto.response.*;
import com.javaweb.users_service.entity.RoleEntity;
import com.javaweb.users_service.entity.UserEntity;
import com.javaweb.users_service.enums.UserStatus;
import com.javaweb.users_service.exception.customexception.BadRequestException;
import com.javaweb.users_service.exception.customexception.UnauthorizedException;
import com.javaweb.users_service.repository.AuthRepository;
import com.javaweb.users_service.repository.RoleRepository;
import com.javaweb.users_service.services.IAuthServices;
import com.javaweb.users_service.util.JwtTokenUtil;
import com.javaweb.users_service.util.OtpUtil;
import com.javaweb.users_service.util.ResponseUtils;
import lombok.RequiredArgsConstructor;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

import java.time.Duration;
import java.time.Instant;
import java.util.UUID;

@RequiredArgsConstructor
@Service
public class AuthService implements IAuthServices {

    private final AuthRepository authRepository;
    private final RoleRepository roleRepository;
    private final PasswordEncoder passwordEncoder;
    private final JwtTokenUtil jwtTokenUtil;
    private final AuthenticationManager authenticationManager;
    private final StringRedisTemplate redisTemplate;
    private final MailQueueService mailQueueService;

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
        RoleEntity roleEntity = roleRepository.findByName("USER")
                .orElseThrow(() -> new BadRequestException("Role not found!"));
        UserEntity newUser = UserEntity.builder()
                .fullName(signUpRequest.getFullName())
                .email(signUpRequest.getEmail())
                .phoneNumber(signUpRequest.getPhoneNumber())
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
        UsernamePasswordAuthenticationToken authenticationToken =new UsernamePasswordAuthenticationToken(loginRequest.getEmail(), loginRequest.getPassword());

        Authentication authentication = authenticationManager.authenticate(authenticationToken);

        UserEntity user = (UserEntity) authentication.getPrincipal();

        String accessToken = jwtTokenUtil.generateAccessToken(user);
        String refreshToken = jwtTokenUtil.generateRefreshToken(user);
        LoginResponse loginResponse = LoginResponse.builder()
                .accessToken(accessToken)
                .refreshToken(refreshToken)
                .build();
        return ResponseUtils.success("Login success full!", loginResponse);
    }

    @Override
    public BaseResponse<Void> logout(String accessTokenId, String refreshToken, Instant expiredAt) {
        if (accessTokenId == null || accessTokenId.isBlank()) {
            throw new BadRequestException("Token is empty!");
        }
        Duration ttlAccess = Duration.between(Instant.now(), expiredAt == null ? Instant.now() : expiredAt);
        if (ttlAccess.isZero() || ttlAccess.isNegative()) {
            ttlAccess = Duration.ofSeconds(30);
        }

        String accessKey = "blacklist:access:" + accessTokenId;
        redisTemplate.opsForValue().set(accessKey, "1", ttlAccess);

        if (refreshToken != null && !refreshToken.isBlank()) {
            String refreshTokenId = jwtTokenUtil.extractRefreshTokenId(refreshToken);
            Instant refreshExpiredAt = jwtTokenUtil.extractRefreshExpiration(refreshToken);
            Duration ttlRefresh = Duration.between(
                    Instant.now(),
                    refreshExpiredAt == null ? Instant.now() : refreshExpiredAt
            );
            if (!ttlRefresh.isZero() && !ttlRefresh.isNegative()) {
                String refreshKey = "blacklist:refresh:" + refreshTokenId;
                redisTemplate.opsForValue().set(refreshKey, "1", ttlRefresh);
            }
        }

        return ResponseUtils.success("Logout successful!");
    }

    @Override
    public BaseResponse<Void> changePass(ChangePassRequest changePassRequest, Long userId) {
        if(!changePassRequest.getNewPassword().equals(changePassRequest.getNewPasswordConfirm())){
            throw new BadRequestException("Passwords do not match!");
        }
        UserEntity user = authRepository.findById(userId)
                .orElseThrow(() -> new BadRequestException("User not found!"));

        if(!passwordEncoder.matches(changePassRequest.getOldPassword(), user.getPassword())){
            throw new BadRequestException("Old password do not sure!");
        }
        Instant now = Instant.now();
        user.setPassword(passwordEncoder.encode(changePassRequest.getNewPassword()));
        authRepository.save(user);

        String key = "changeAt:" + userId;
        redisTemplate.opsForValue().set(key, String.valueOf(now.toEpochMilli()));
        return ResponseUtils.success("Change password successful!");
    }

    @Override
    public BaseResponse<CheckMailResponse> checkMail(String email) {
        UserEntity user = authRepository.findByEmailAndStatusAndDeletedFalse(email, UserStatus.ACTIVE)
                .orElseThrow(() -> new BadRequestException("Email not found!"));
        Long userId = user.getId();
        String otp = OtpUtil.generateOtp();
        String hashedOtp = passwordEncoder.encode(otp);
        String key = "checkMail:" + user.getId();

        redisTemplate.opsForValue().set(key, hashedOtp, Duration.ofSeconds(120));
        mailQueueService.enqueueOtpMail(email, otp);

        CheckMailResponse checkMailResponse = CheckMailResponse.builder()
                .userId(userId)
                .build();
        return ResponseUtils.success("Mail sent!", checkMailResponse);
    }

    @Override
    public BaseResponse<CheckOTPResponse> checkOtp(String OTP, Long userId) {
        String key = "checkMail:" + userId;
        String hashedOtp = redisTemplate.opsForValue().get(key);
        if(hashedOtp == null || hashedOtp.isBlank()){
            throw new BadRequestException("OTP is empty!");
        }
        if(!passwordEncoder.matches(OTP, hashedOtp)){
            throw  new BadRequestException("Wrong OTP!");
        }
        String token = UUID.randomUUID().toString();
        String keyToken = "checkOTP:"+ userId;
        redisTemplate.opsForValue().set(keyToken, token, Duration.ofSeconds(120));
        CheckOTPResponse otpResponse = CheckOTPResponse.builder()
                .userId(userId)
                .token(token)
                .build();

        redisTemplate.delete(key);
        return ResponseUtils.success("Check OTP successful!", otpResponse);
    }

    @Override
    public BaseResponse<Void> resetPassword(ResetPasswordRequest resetPasswordRequest) {
        String key = "checkOTP:"+ resetPasswordRequest.getUserId();
        String tokenRedis =  redisTemplate.opsForValue().get(key);

        if(tokenRedis == null || tokenRedis.isBlank()){
            throw new BadRequestException("Token is empty!");
        }
        if(!tokenRedis.equals(resetPasswordRequest.getToken())){
            throw new BadRequestException("Wrong Token!");
        }

        Instant now = Instant.now();

        UserEntity user = authRepository.findById(resetPasswordRequest.getUserId())
                .orElseThrow(() -> new BadRequestException("User not found!"));
        user.setPassword(passwordEncoder.encode(resetPasswordRequest.getNewPassword()));

        authRepository.save(user);

        String keyChange = "changeAt:" + resetPasswordRequest.getUserId();
        redisTemplate.opsForValue().set(keyChange, String.valueOf(now.toEpochMilli()));

        redisTemplate.delete(key);

        return ResponseUtils.success("Reset Password successful!");
    }

    @Override
    public BaseResponse<RefreshResponse> refreshToken(LogoutRequest refreshToken) {
        if (refreshToken.getRefreshToken() == null || refreshToken.getRefreshToken().isBlank()) {
            throw new BadRequestException("Refresh token is empty!");
        }

        String refreshTokenId = jwtTokenUtil.extractRefreshTokenId(refreshToken.getRefreshToken());
        String refreshKey = "blacklist:refresh:" + refreshTokenId;
        if (redisTemplate.hasKey(refreshKey)) {
            throw new UnauthorizedException("Refresh token revoked!");
        }

        Long userId = jwtTokenUtil.extractRefreshUserId(refreshToken.getRefreshToken());
        if (userId == null) {
            throw new UnauthorizedException("Invalid refresh token!");
        }

        String changeAtValue = redisTemplate.opsForValue().get("changeAt:" + userId);
        if (changeAtValue != null && !changeAtValue.isBlank()) {
            try {
                long changeAtMs = Long.parseLong(changeAtValue);
                Instant issuedAt = jwtTokenUtil.extractRefreshIssuedAt(refreshToken.getRefreshToken());
                if (issuedAt != null && issuedAt.toEpochMilli() <= changeAtMs) {
                    throw new UnauthorizedException("Refresh token invalid after password change!");
                }
            } catch (NumberFormatException e) {
                throw new UnauthorizedException("Invalid password change time!");
            }
        }

        UserEntity user = authRepository.findById(userId)
                .orElseThrow(() -> new BadRequestException("User not found!"));
        String newAccessToken = jwtTokenUtil.generateAccessToken(user);
        RefreshResponse access = RefreshResponse.builder()
                .accessToken(newAccessToken)
                .build();
        return ResponseUtils.success("Refresh token successful!", access);
    }

}
