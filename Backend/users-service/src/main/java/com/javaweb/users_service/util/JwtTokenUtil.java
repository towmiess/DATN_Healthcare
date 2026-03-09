package com.javaweb.users_service.util;


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
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.stereotype.Component;

import javax.crypto.SecretKey;
import java.security.Key;
import java.time.Instant;
import java.util.*;
import java.util.function.Function;

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

    //sinh token
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

    //tạo access token:
    public String generateAccessToken(UserEntity user){
        return generateToken(user, expirationAccess, secretAccess);
    }

    //tạo refresh token:
    public String generateRefreshToken(UserEntity user){
        return generateToken(user, expirationRefresh,  secretRefresh);
    }

    //tạo khóa bí mật dùng trong tạo token và xác thực
    private Key getSignInKey(String secretkey) {
        byte[] bytes = Decoders.BASE64.decode(secretkey);
        return Keys.hmacShaKeyFor(bytes);
    }

    //dùng để đọc và xác thực jwt rồi lấy toàn bộ thông tin
    private Claims extractAllClaims(String token, String secret) {
        try{
            return Jwts.parser()
                    .verifyWith((SecretKey) getSignInKey(secret))
                    .build()
                    .parseSignedClaims(token)
                    .getPayload();
        }catch(ExpiredJwtException e){
            throw new UnauthorizedException("RefreshToken is expired or not valid!");
        }catch (JwtException e){
            throw new UnauthorizedException("Invalid JWT token!");
        }

    }

    //áp dụng T class dùng để lấy thông tin trong token 1 cách linh động
    public  <T> T extractClaim(String token, Function<Claims, T> claimsResolver,  String secret) {
        final Claims claims = this.extractAllClaims(token, secret);
        return claimsResolver.apply(claims);
    }

    //check hạn token
    public boolean isTokenExpired(String token, String secret) {
        Date expirationDate = this.extractClaim(token, Claims::getExpiration, secret);
        return expirationDate.before(new Date());
    }

    //lấy username
    public String extractUsername(String token, String secret) {
        return extractClaim(token, Claims::getSubject, secret);
    }
    //lấy user_id
    public Long extractUserId(String token, String secret) {
        return extractClaim(token, claims -> {
            Object userId = claims.get("user_id");
            if (userId instanceof Integer) {
                return ((Integer) userId).longValue();
            }
            return (Long) userId;
        }, secret);
    }
    //lấy roles
    public List<String> extractRoles(String token, String secret) {
        return extractClaim(token, claims -> {
            Object roles = claims.get("roles");

            if (roles instanceof List<?>) {
                return ((List<?>) roles)
                        .stream()
                        .map(Object::toString)
                        .toList();
            }

            return List.of();
        }, secret);
    }



    //lấy token id
    public String tokenId(String token, String secret) {
        return extractClaim(token, Claims::getId, secret);
    }
    //lấy thời gian tạo
    public Instant tokenIssuedAtInstant(String token, String secret) {
        Date issuedAt = extractClaim(token, Claims::getIssuedAt, secret);
        return issuedAt != null ? issuedAt.toInstant() : null;
    }


    //xác định token là của người dùng nào và kiểm tra hạn
    public boolean validateToken(String token, UserDetails userDetails, String secret) {
        UserEntity user = (UserEntity) userDetails;
        if (!extractUsername(token, secret).equals(user.getUsername())) {
            return false;
        }
        if (isTokenExpired(token, secret)) {
            return false;
        }

        Instant changePassAt = user.getChangePassAt();
        if(changePassAt != null){
            Instant issuedAt = tokenIssuedAtInstant(token, secret);
            return !issuedAt.isBefore(changePassAt);
        }
        return true;
    }
}