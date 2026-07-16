package com.javaweb.nutrition_service.dto.request;

import lombok.Getter;
import lombok.Setter;

@Getter
@Setter
public class NutritionMealTemplateAdminQueryRequest {
    private Integer page;
    private Integer size;
    private String keyword;
    private String mealType;
}
