package com.javaweb.nutrition_service.config;

import com.javaweb.nutrition_service.filter.GatewaySignatureFilter;
import com.javaweb.nutrition_service.util.SecurityResponseUtil;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpMethod;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.annotation.web.configurers.AbstractHttpConfigurer;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;

@Configuration
@EnableWebSecurity
public class WebSecurityConfig {

    private final GatewaySignatureFilter gatewaySignatureFilter;

    public WebSecurityConfig(GatewaySignatureFilter gatewaySignatureFilter) {
        this.gatewaySignatureFilter = gatewaySignatureFilter;
    }

    @Bean
    public SecurityFilterChain securityFilterChain(HttpSecurity http) throws Exception {
        http
                .csrf(AbstractHttpConfigurer::disable)
                .addFilterBefore(gatewaySignatureFilter, UsernamePasswordAuthenticationFilter.class)
                .exceptionHandling(exception -> exception
                        .authenticationEntryPoint((request, response, authException) ->
                                SecurityResponseUtil.sendUnauthorized(response, "Unauthorized!"))
                        .accessDeniedHandler((request, response, accessDeniedException) ->
                                SecurityResponseUtil.sendForbidden(response, "Forbidden: admin role required"))
                )
                .authorizeHttpRequests(requests -> requests
                        .requestMatchers(HttpMethod.OPTIONS, "/**").permitAll()
                        .requestMatchers(
                                HttpMethod.POST,
                                "/api/nutrition/meal-templates",
                                "/api/nutrition/meal-templates/batch"
                        ).hasRole("ADMIN")
                        .requestMatchers(
                                HttpMethod.GET,
                                "/api/nutrition/meal-templates"
                        ).hasRole("ADMIN")
                        .requestMatchers(
                                HttpMethod.GET,
                                "/api/nutrition/meal-templates/recommendations",
                                "/api/meal-history"
                        ).authenticated()
                        .anyRequest().authenticated()
                );

        return http.build();
    }
}
