package com.javaweb.nutrition_service.repository;

import com.javaweb.nutrition_service.entity.IngredientEntity;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface IngredientRepositoryCustom {

    List<IngredientEntity> searchCandidates(
            String exactFoodName,
            String exactNormalizedName,
            String foodNamePrefix,
            String normalizedNamePrefix,
            String foodNameContains,
            String normalizedNameContains,
            int limit
    );
}
