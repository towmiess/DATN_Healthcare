package com.javaweb.nutrition_service.util;

import com.javaweb.nutrition_service.dto.request.IngredientCreateRequest;
import com.javaweb.nutrition_service.dto.response.IngredientResponse;
import com.javaweb.nutrition_service.entity.IngredientEntity;
import org.springframework.beans.BeanUtils;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;

import java.text.Normalizer;
import java.util.List;
import java.util.Locale;

@Component
public class IngredientMapperUtil {

    public IngredientEntity toEntity(IngredientCreateRequest request) {
        IngredientEntity entity = new IngredientEntity();
        BeanUtils.copyProperties(request, entity);

        String foodName = normalizeDisplayName(request.getFoodName());
        String normalizedName = normalizeKey(
                StringUtils.hasText(request.getNormalizedName()) ? request.getNormalizedName() : foodName
        );

        entity.setFoodName(foodName);
        entity.setNormalizedName(normalizedName);
        return entity;
    }

    public List<IngredientEntity> toEntities(List<IngredientCreateRequest> requests) {
        if (requests == null || requests.isEmpty()) {
            return List.of();
        }
        return requests.stream()
                .map(this::toEntity)
                .toList();
    }

    public IngredientResponse toResponse(IngredientEntity entity) {
        IngredientResponse response = new IngredientResponse();
        BeanUtils.copyProperties(entity, response);
        return response;
    }

    public List<IngredientResponse> toResponses(List<IngredientEntity> entities) {
        if (entities == null || entities.isEmpty()) {
            return List.of();
        }
        return entities.stream()
                .map(this::toResponse)
                .toList();
    }

    public String normalizeDisplayName(String value) {
        if (!StringUtils.hasText(value)) {
            return "";
        }
        return value.trim().replaceAll("\\s+", " ");
    }

    public String normalizeKey(String value) {
        if (!StringUtils.hasText(value)) {
            return "";
        }

        String normalized = Normalizer.normalize(value, Normalizer.Form.NFD)
                .replaceAll("\\p{M}+", "");

        return normalized
                .toLowerCase(Locale.ROOT)
                .replaceAll("[^\\p{L}\\p{Nd}]+", " ")
                .trim()
                .replaceAll("\\s+", " ");
    }
}
