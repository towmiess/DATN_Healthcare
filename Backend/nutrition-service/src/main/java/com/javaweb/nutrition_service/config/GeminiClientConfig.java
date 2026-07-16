package com.javaweb.nutrition_service.config;

import lombok.RequiredArgsConstructor;
import org.springframework.boot.web.client.RestTemplateBuilder;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.client.RestTemplate;

@Configuration
@RequiredArgsConstructor
public class GeminiClientConfig {

    private final GeminiVisionProperties geminiVisionProperties;

    @Bean
    public RestTemplate geminiRestTemplate(RestTemplateBuilder builder) {
        return builder
                .setConnectTimeout(geminiVisionProperties.getConnectTimeout())
                .setReadTimeout(geminiVisionProperties.getReadTimeout())
                .build();
    }
}
