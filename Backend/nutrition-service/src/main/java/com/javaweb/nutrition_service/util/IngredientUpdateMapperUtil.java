package com.javaweb.nutrition_service.util;

import com.javaweb.nutrition_service.dto.request.IngredientUpdateRequest;
import com.javaweb.nutrition_service.entity.IngredientEntity;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;

@Component
@RequiredArgsConstructor
public class IngredientUpdateMapperUtil {

    private final IngredientMapperUtil ingredientMapperUtil;

    public void applyUpdate(IngredientEntity target, IngredientUpdateRequest request) {
        if (target == null || request == null) {
            return;
        }

        if (StringUtils.hasText(request.getFoodName())) {
            target.setFoodName(ingredientMapperUtil.normalizeDisplayName(request.getFoodName()));
        }
        if (StringUtils.hasText(request.getNormalizedName())) {
            target.setNormalizedName(ingredientMapperUtil.normalizeKey(request.getNormalizedName()));
        } else if (StringUtils.hasText(request.getFoodName())) {
            target.setNormalizedName(ingredientMapperUtil.normalizeKey(request.getFoodName()));
        }
        if (request.getCalories() != null) {
            target.setCalories(request.getCalories());
        }
        if (request.getProtein() != null) {
            target.setProtein(request.getProtein());
        }
        if (request.getFat() != null) {
            target.setFat(request.getFat());
        }
        if (request.getCarbs() != null) {
            target.setCarbs(request.getCarbs());
        }
    }
}
