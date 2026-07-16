package com.javaweb.nutrition_service.util;

import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.Collection;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;

@Component
public class NutritionMealTemplateQueryUtil {

    public List<String> normalizeUserTypes(Collection<String> userTypes) {
        if (userTypes == null || userTypes.isEmpty()) {
            return List.of();
        }

        Set<String> normalized = new LinkedHashSet<>();
        for (String userType : userTypes) {
            if (userType == null || userType.isBlank()) {
                continue;
            }

            String normalizedUserType = userType.trim().toLowerCase(Locale.ROOT);
            if ("none".equals(normalizedUserType)) {
                return List.of();
            }

            normalized.add(normalizedUserType);
        }

        return new ArrayList<>(normalized);
    }

    public String toCondition(String userType) {
        return switch (userType) {
            case "suitable_type1" -> "suitable_type1 = true";
            case "suitable_type2" -> "suitable_type2 = true";
            case "suitable_gestational" -> "suitable_gestational = true";
            case "suitable_neuropathy" -> "suitable_neuropathy = true";
            case "suitable_cardiovascular" -> "suitable_cardiovascular = true";
            case "suitable_stroke" -> "suitable_stroke = true";
            default -> null;
        };
    }
}
