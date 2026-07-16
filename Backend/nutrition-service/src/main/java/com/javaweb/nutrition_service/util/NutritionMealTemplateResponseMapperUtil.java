package com.javaweb.nutrition_service.util;

import com.javaweb.nutrition_service.dto.response.NutritionMealTemplateResponse;
import com.javaweb.nutrition_service.entity.NutritionMealTemplateEntity;
import org.springframework.beans.BeanUtils;
import org.springframework.stereotype.Component;

import java.util.List;

@Component
public class NutritionMealTemplateResponseMapperUtil {

    public NutritionMealTemplateResponse toResponse(NutritionMealTemplateEntity entity) {
        NutritionMealTemplateResponse response = new NutritionMealTemplateResponse();
        BeanUtils.copyProperties(entity, response);
        return response;
    }

    public List<NutritionMealTemplateResponse> toResponses(List<NutritionMealTemplateEntity> entities) {
        if (entities == null || entities.isEmpty()) {
            return List.of();
        }

        return entities.stream()
                .map(this::toResponse)
                .toList();
    }
}
