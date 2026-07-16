package com.javaweb.nutrition_service.filter;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.JsonNode;
import com.javaweb.nutrition_service.dto.TokenPayload;
import com.javaweb.nutrition_service.util.GatewaySignatureUtil;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.NonNull;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpMethod;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.util.List;
import java.util.Base64;
import java.util.Collection;
import java.util.ArrayList;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;

@Component
@RequiredArgsConstructor
public class GatewaySignatureFilter extends OncePerRequestFilter {

    private final GatewaySignatureUtil gatewaySignatureUtil;
    private final ObjectMapper objectMapper;

    @Override
    protected void doFilterInternal(
            @NonNull HttpServletRequest request,
            @NonNull HttpServletResponse response,
            @NonNull FilterChain filterChain
    ) throws ServletException, IOException {
        if (HttpMethod.OPTIONS.matches(request.getMethod())) {
            filterChain.doFilter(request, response);
            return;
        }

        String encodedPayload = request.getHeader("X-User-Context");
        String signature = request.getHeader("X-User-Context-Signature");

        if (encodedPayload == null) {
            encodedPayload = "";
        }

        if (!gatewaySignatureUtil.isValidGatewaySignature(encodedPayload, signature)) {
            response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
            response.setContentType("application/json");
            response.getWriter().write("{\"message\":\"Invalid gateway signature\"}");
            return;
        }

        if (encodedPayload.isBlank()) {
            response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
            response.setContentType("application/json");
            response.getWriter().write("{\"message\":\"Missing user context\"}");
            return;
        }

        try {
            byte[] decoded = Base64.getDecoder().decode(encodedPayload);
            JsonNode root = objectMapper.readTree(decoded);
            TokenPayload context = new TokenPayload();
            context.setUserId(root.path("userId").isNumber() ? root.path("userId").asLong() : null);
            context.setUsername(root.path("username").asText(null));
            context.setTokenId(root.path("tokenId").asText(null));
            context.setTokenCreatedAt(parseInstant(root.path("tokenCreatedAt")));
            context.setTokenExpiredAt(parseInstant(root.path("tokenExpiredAt")));

            List<String> roles = new ArrayList<>();
            JsonNode rolesNode = root.path("roles");
            if (rolesNode.isArray()) {
                for (JsonNode roleNode : rolesNode) {
                    String role = roleNode.asText("").trim();
                    if (!role.isEmpty()) {
                        roles.add(role);
                    }
                }
            }
            context.setRoles(roles);

            Collection<? extends GrantedAuthority> authorities =
                    context.getRoles() == null ? List.of() : context.getRoles().stream()
                            .map(String::trim)
                            .filter(role -> !role.isEmpty())
                            .map(role -> role.startsWith("ROLE_") ? role : "ROLE_" + role)
                            .map(String::toUpperCase)
                            .map(SimpleGrantedAuthority::new)
                            .toList();

            UsernamePasswordAuthenticationToken authentication =
                    new UsernamePasswordAuthenticationToken(context, null, authorities);
            SecurityContextHolder.getContext().setAuthentication(authentication);

            filterChain.doFilter(request, response);
        } catch (Exception exception) {
            response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
            response.setContentType("application/json");
            response.getWriter().write("{\"message\":\"Invalid user context\"}");
        } finally {
            SecurityContextHolder.clearContext();
        }
    }

    private java.time.Instant parseInstant(JsonNode node) {
        if (node == null || node.isMissingNode() || node.isNull()) {
            return null;
        }
        try {
            if (node.isNumber()) {
                return java.time.Instant.ofEpochMilli(node.asLong());
            }
            String text = node.asText("").trim();
            if (text.isEmpty()) {
                return null;
            }
            return java.time.Instant.parse(text);
        } catch (Exception ignored) {
            return null;
        }
    }
}
