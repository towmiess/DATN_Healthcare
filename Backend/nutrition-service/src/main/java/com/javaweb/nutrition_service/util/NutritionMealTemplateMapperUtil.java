package com.javaweb.nutrition_service.util;

import com.javaweb.nutrition_service.dto.request.NutritionMealTemplateCreateRequest;
import com.javaweb.nutrition_service.entity.NutritionMealTemplateEntity;
import org.springframework.beans.BeanUtils;
import org.springframework.stereotype.Component;

import java.util.List;

@Component
public class NutritionMealTemplateMapperUtil {

    public NutritionMealTemplateEntity toEntity(NutritionMealTemplateCreateRequest request) {
        NutritionMealTemplateEntity mealTemplate = new NutritionMealTemplateEntity();
        BeanUtils.copyProperties(request, mealTemplate);
        return mealTemplate;
    }

    public List<NutritionMealTemplateEntity> toEntities(List<NutritionMealTemplateCreateRequest> requests) {
        if (requests == null || requests.isEmpty()) {
            return List.of();
        }
        return requests.stream()
                .map(this::toEntity)
                .toList();
    }
}
