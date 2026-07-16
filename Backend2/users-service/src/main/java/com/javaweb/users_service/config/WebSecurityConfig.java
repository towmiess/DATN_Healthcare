package com.javaweb.users_service.config;

import com.javaweb.users_service.filter.JwtTokenFilter;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpMethod;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.annotation.web.configurers.AbstractHttpConfigurer;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;

import java.io.IOException;

import static com.javaweb.users_service.util.ExceptionUtils.sendForbidden;
import static com.javaweb.users_service.util.ExceptionUtils.sendUnauthorized;

@Configuration
@EnableWebSecurity
public class WebSecurityConfig {

    private final JwtTokenFilter jwtTokenFilter;

    public WebSecurityConfig(JwtTokenFilter jwtTokenFilter) {
        this.jwtTokenFilter = jwtTokenFilter;
    }

    @Bean
    public SecurityFilterChain securityFilterChain(HttpSecurity http) throws Exception {

        http
                .csrf(AbstractHttpConfigurer::disable)
                .addFilterBefore(jwtTokenFilter, UsernamePasswordAuthenticationFilter.class)
                .exceptionHandling(exception -> exception
                        .authenticationEntryPoint((request, response, authException) ->
                                sendUnauthorized(response, "Unauthorized!"))
                        .accessDeniedHandler((request, response, accessDeniedException) ->
                                sendForbidden(response, "Forbidden: admin role required"))
                )
                .authorizeHttpRequests(requests -> {
                    requests
                            .requestMatchers(HttpMethod.OPTIONS, "/**").permitAll()
                            .requestMatchers("/api/auth/signup", "/api/auth/signin", "/api/auth/check-mail", "/api/auth/check-otp", "/api/auth/reset-password", "/api/auth/refresh-token", "/api/users/count")
                            .permitAll()
                            .requestMatchers("/api/users/**").hasRole("ADMIN")
                            .anyRequest().authenticated();
                });

        return http.build();
    }
}
