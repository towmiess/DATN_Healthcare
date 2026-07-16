package com.javaweb.nutrition_service.util;

import com.javaweb.nutrition_service.dto.response.VisionAnalyzeResponse;
import com.javaweb.nutrition_service.dto.response.MealHistoryResponse;
import com.javaweb.nutrition_service.entity.MealHistoryEntity;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.List;
import java.util.Objects;

@Component
public class MealHistoryMapperUtil {

    public MealHistoryEntity toEntity(
            Long userId,
            String image,
            String name,
            BigDecimal totalCalories,
            BigDecimal totalProtein,
            BigDecimal totalFat,
            BigDecimal totalCarbs
    ) {
        return MealHistoryEntity.builder()
                .userId(userId)
                .image(image)
                .name(name)
                .totalCalories(normalize(totalCalories))
                .totalProtein(normalize(totalProtein))
                .totalFat(normalize(totalFat))
                .totalCarbs(normalize(totalCarbs))
                .build();
    }

    public VisionAnalyzeResponse toResponse(MealHistoryEntity entity) {
        return VisionAnalyzeResponse.builder()
                .name(defaultString(entity.getName()))
                .image(defaultString(entity.getImage()))
                .totalCalories(normalize(entity.getTotalCalories()))
                .totalProtein(normalize(entity.getTotalProtein()))
                .totalFat(normalize(entity.getTotalFat()))
                .totalCarbs(normalize(entity.getTotalCarbs()))
                .createdAt(entity.getCreatedAt())
                .build();
    }

    public MealHistoryResponse toHistoryResponse(MealHistoryEntity entity) {
        return MealHistoryResponse.builder()
                .id(entity.getId())
                .image(defaultString(entity.getImage()))
                .name(defaultString(entity.getName()))
                .totalCalories(normalize(entity.getTotalCalories()))
                .totalProtein(normalize(entity.getTotalProtein()))
                .totalFat(normalize(entity.getTotalFat()))
                .totalCarbs(normalize(entity.getTotalCarbs()))
                .createdAt(entity.getCreatedAt())
                .build();
    }

    public List<MealHistoryResponse> toHistoryResponses(List<MealHistoryEntity> entities) {
        if (entities == null || entities.isEmpty()) {
            return List.of();
        }

        return entities.stream()
                .map(this::toHistoryResponse)
                .toList();
    }

    private BigDecimal normalize(BigDecimal value) {
        return Objects.requireNonNullElse(value, BigDecimal.ZERO).setScale(2, RoundingMode.HALF_UP);
    }

    private String defaultString(String value) {
        return value == null ? "" : value;
    }
}
