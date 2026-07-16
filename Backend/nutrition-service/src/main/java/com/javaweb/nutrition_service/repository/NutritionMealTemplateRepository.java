package com.javaweb.nutrition_service.repository;

import com.javaweb.nutrition_service.entity.NutritionMealTemplateEntity;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface NutritionMealTemplateRepository extends JpaRepository<NutritionMealTemplateEntity, Long>, NutritionMealTemplateRepositoryCustom {
}
