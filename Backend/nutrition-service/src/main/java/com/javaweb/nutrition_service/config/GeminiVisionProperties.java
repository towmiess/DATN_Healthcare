package com.javaweb.nutrition_service.config;

import lombok.Getter;
import lombok.Setter;
import org.springframework.boot.context.properties.ConfigurationProperties;

import java.time.Duration;

@Getter
@Setter
@ConfigurationProperties(prefix = "app.gemini")
public class GeminiVisionProperties {

    private String apiKey;

    private String baseUrl = "https://generativelanguage.googleapis.com/v1beta";

    private String model = "gemini-2.5-flash";

    private Duration connectTimeout = Duration.ofSeconds(10);

    private Duration readTimeout = Duration.ofSeconds(60);
}
