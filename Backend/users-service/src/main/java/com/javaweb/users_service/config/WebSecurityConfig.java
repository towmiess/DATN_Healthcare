package com.javaweb.users_service.config;

import com.javaweb.users_service.filter.JwtTokenFilter;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.annotation.web.configurers.AbstractHttpConfigurer;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;

import static org.springframework.http.HttpMethod.GET;

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
                .authorizeHttpRequests(requests -> {
                    requests
                            .requestMatchers("/api/auth/signup", "/api/auth/signin", "/api/auth/check-mail", "/api/auth/check-otp", "/api/auth/reset-password", "/api/auth/refresh-token")
                            .permitAll()
                            .requestMatchers(GET,"/api/users").hasRole("ADMIN")
                            .anyRequest().authenticated();
                });

        return http.build();
    }
}
