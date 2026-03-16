package com.javaweb.users_service.filter;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.javaweb.users_service.dto.TokenPayload;
import com.javaweb.users_service.mapper.UserMapper;
import com.javaweb.users_service.util.JwtTokenUtil;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.NonNull;
import lombok.RequiredArgsConstructor;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.web.authentication.WebAuthenticationDetailsSource;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.util.Base64;
import java.util.Collection;

@Component
@RequiredArgsConstructor
public class JwtTokenFilter extends OncePerRequestFilter {

    private final ObjectMapper objectMapper;
    private final JwtTokenUtil jwtTokenUtil;
    private final UserMapper userMapper;

    @Override
    protected void doFilterInternal(
            @NonNull HttpServletRequest request,
            @NonNull HttpServletResponse response,
            @NonNull FilterChain filterChain
    ) throws ServletException, IOException {

        String encodedPayload = request.getHeader("X-User-Context");
        String signature = request.getHeader("X-User-Context-Signature");

        if (encodedPayload == null) {
            encodedPayload = "";
        }

        if (!jwtTokenUtil.isValidGatewaySignature(encodedPayload, signature)) {
            response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
            response.setContentType("application/json");
            response.getWriter().write("{\"message\":\"Invalid gateway signature\"}");
            return;
        }

        if (encodedPayload.isBlank()) {
            filterChain.doFilter(request, response);
            return;
        }

        TokenPayload context;
        try {
            byte[] decoded = Base64.getDecoder().decode(encodedPayload);
            context = objectMapper.readValue(decoded, TokenPayload.class);
        } catch (Exception e) {
            response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
            response.setContentType("application/json");
            response.getWriter().write("{\"message\":\"Invalid user context\"}");
            return;
        }

        if (context != null
                && SecurityContextHolder.getContext().getAuthentication() == null) {

            Collection<? extends GrantedAuthority> authorities =
                    userMapper.toRoles(context.getRoles()).stream()
                            .map(String::trim)
                            .filter(role -> !role.isEmpty())
                            .map(role -> role.startsWith("ROLE_") ? role : "ROLE_" + role)
                            .map(String::toUpperCase)
                            .map(SimpleGrantedAuthority::new)
                            .toList();

            UsernamePasswordAuthenticationToken authentication =
                    new UsernamePasswordAuthenticationToken(
                            jwtTokenUtil.resolvePrincipal(context),
                            null,
                            authorities
                    );

            authentication.setDetails(
                    new WebAuthenticationDetailsSource().buildDetails(request)
            );

            SecurityContextHolder.getContext().setAuthentication(authentication);
        }

        filterChain.doFilter(request, response);
    }
}
