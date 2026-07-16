package com.javaweb.nutrition_service.services;

import com.javaweb.nutrition_service.dto.response.MealRecommendationResponse;
import com.javaweb.nutrition_service.dto.request.NutritionMealTemplateAdminQueryRequest;
import com.javaweb.nutrition_service.dto.request.NutritionMealTemplateCreateRequest;
import com.javaweb.nutrition_service.dto.request.NutritionMealTemplateUpdateRequest;
import com.javaweb.nutrition_service.dto.response.NutritionMealTemplatePageResponse;
import com.javaweb.nutrition_service.entity.NutritionMealTemplateEntity;

import java.util.List;

public interface INutritionMealTemplateService {
    NutritionMealTemplateEntity create(NutritionMealTemplateCreateRequest request);
    List<NutritionMealTemplateEntity> createAll(List<NutritionMealTemplateCreateRequest> requests);
    NutritionMealTemplateEntity update(Long id, NutritionMealTemplateUpdateRequest request);
    void delete(Long id);
    NutritionMealTemplatePageResponse getAdminMeals(NutritionMealTemplateAdminQueryRequest request);
    MealRecommendationResponse recommendRandomMealsForCurrentUser();
}
