package com.javaweb.nutrition_service.repository;

import com.javaweb.nutrition_service.entity.NutritionMealTemplateEntity;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface NutritionMealTemplateRepositoryCustom {

    List<NutritionMealTemplateEntity> findRandomRecommendedMeals(List<String> userTypes, int limit);

    Page<NutritionMealTemplateEntity> findAdminMeals(String keyword, String mealType, Pageable pageable);
}
