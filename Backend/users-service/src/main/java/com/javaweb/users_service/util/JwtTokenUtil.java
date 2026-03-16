package com.javaweb.users_service.util;


import com.javaweb.users_service.dto.TokenPayload;
import com.javaweb.users_service.entity.RoleEntity;
import com.javaweb.users_service.entity.UserEntity;
import com.javaweb.users_service.exception.customexception.JwtGenerationException;
import com.javaweb.users_service.exception.customexception.UnauthorizedException;
import io.jsonwebtoken.Claims;
import io.jsonwebtoken.ExpiredJwtException;
import io.jsonwebtoken.JwtException;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.io.Decoders;
import io.jsonwebtoken.security.Keys;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import javax.crypto.Mac;
import javax.crypto.SecretKey;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.security.Key;
import java.security.MessageDigest;
import java.time.Instant;
import java.util.*;

@Component
@RequiredArgsConstructor
public class JwtTokenUtil {
    @Value("${jwt.access.expiration}")
    private Long expirationAccess;

    @Value("${jwt.refresh.expiration}")
    private Long expirationRefresh;

    @Value("${jwt.access.secret}")
    private String secretAccess;

    @Value("${jwt.refresh.secret}")
    private String secretRefresh;

    @Value("${app.gateway.internal-secret}")
    private String internalSecret;

    // Tạo JWT cho user với thời hạn và khóa bí mật.
    public String generateToken(UserEntity user, Long expirationTime, String secret){
        Map<String, Object> claims = new HashMap<>();
        claims.put("user_id", user.getId());
        claims.put("roles", user.getRoleEntities().stream().map(RoleEntity::getName).toList());
        try {
            return Jwts.builder()
                    .claims(claims)
                    .subject(user.getUsername())
                    .expiration(new Date(System.currentTimeMillis() + expirationTime))
                    .id(UUID.randomUUID().toString())
                    .issuedAt(new Date())
                    .signWith(getSignInKey(secret))
                    .compact();
        }catch (JwtException e){
            throw new JwtGenerationException("Can not create JWT" + e.getMessage());
        }
    }

    // Tạo access token.
    public String generateAccessToken(UserEntity user){
        return generateToken(user, expirationAccess, secretAccess);
    }

    // Tạo refresh token.
    public String generateRefreshToken(UserEntity user){
        return generateToken(user, expirationRefresh,  secretRefresh);
    }

    // Tao khoa ky JWT tu secret base64.
    private Key getSignInKey(String secretkey) {
        byte[] bytes = Decoders.BASE64.decode(secretkey);
        return Keys.hmacShaKeyFor(bytes);
    }

    private Claims extractAllClaims(String token, String secret) {
        try {
            return Jwts.parser()
                    .verifyWith((SecretKey) getSignInKey(secret))
                    .build()
                    .parseSignedClaims(token)
                    .getPayload();
        } catch (ExpiredJwtException e) {
            throw new UnauthorizedException("Token is expired!");
        } catch (JwtException e) {
            throw new UnauthorizedException("Invalid JWT token!");
        }
    }

    public String extractRefreshTokenId(String token) {
        return extractTokenId(token, secretRefresh);
    }

    public Long extractRefreshUserId(String token) {
        return extractUserId(token, secretRefresh);
    }

    public Instant extractRefreshExpiration(String token) {
        return extractExpirationInstant(token, secretRefresh);
    }

    public Instant extractRefreshIssuedAt(String token) {
        return extractIssuedAtInstant(token, secretRefresh);
    }

    private Long extractUserId(String token, String secret) {
        Object userId = extractAllClaims(token, secret).get("user_id");
        if (userId instanceof Integer) {
            return ((Integer) userId).longValue();
        }
        if (userId instanceof Long) {
            return (Long) userId;
        }
        if (userId != null) {
            try {
                return Long.parseLong(userId.toString());
            } catch (NumberFormatException ignored) {
                return null;
            }
        }
        return null;
    }

    private String extractTokenId(String token, String secret) {
        return extractAllClaims(token, secret).getId();
    }

    private Instant extractExpirationInstant(String token, String secret) {
        Date expiration = extractAllClaims(token, secret).getExpiration();
        return expiration != null ? expiration.toInstant() : null;
    }

    private Instant extractIssuedAtInstant(String token, String secret) {
        Date issuedAt = extractAllClaims(token, secret).getIssuedAt();
        return issuedAt != null ? issuedAt.toInstant() : null;
    }

    //Xác nhận request đi qua gateway(chữ ký HMAC).
    public boolean isValidGatewaySignature(String payload, String signature) {
        if (signature == null || signature.isBlank()) {
            return false;
        }
        String expected = sign(payload);
        return MessageDigest.isEqual(
                expected.getBytes(StandardCharsets.UTF_8),
                signature.getBytes(StandardCharsets.UTF_8)
        );
    }

    //Ký payload HMAC-SHA256 cho gateway header.
    private String sign(String payload) {
        try {
            Mac mac = Mac.getInstance("HmacSHA256");
            SecretKeySpec keySpec = new SecretKeySpec(
                    internalSecret.getBytes(StandardCharsets.UTF_8),
                    "HmacSHA256"
            );
            mac.init(keySpec);
            byte[] raw = mac.doFinal(payload.getBytes(StandardCharsets.UTF_8));
            return Base64.getEncoder().encodeToString(raw);
        } catch (Exception e) {
            return "";
        }
    }

    //Trả về principal đầy đủ từ header
    public TokenPayload resolvePrincipal(TokenPayload context) {
        return context;
    }
}
