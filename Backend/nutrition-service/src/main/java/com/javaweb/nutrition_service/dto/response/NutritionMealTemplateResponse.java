package com.javaweb.nutrition_service.dto.response;

import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.math.BigDecimal;

@Getter
@Setter
@Builder
@NoArgsConstructor
@AllArgsConstructor
@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public class NutritionMealTemplateResponse {
    private Long id;
    private String name;
    private String category;
    private String cuisine;
    private String keywords;
    private String description;
    private String prepTime;
    private String cookTime;
    private String totalTime;
    private Integer servings;
    private String servingSize;
    private String glycemicIndex;
    private BigDecimal glycemicLoad;
    private Integer calories;
    private BigDecimal totalFatG;
    private BigDecimal saturatedFatG;
    private BigDecimal transFatG;
    private BigDecimal cholesterolMg;
    private BigDecimal sodiumMg;
    private BigDecimal totalCarbohydrateG;
    private BigDecimal dietaryFiberG;
    private BigDecimal sugarsG;
    private BigDecimal addedSugarsG;
    private BigDecimal proteinG;
    private BigDecimal potassiumMg;
    private BigDecimal phosphorusMg;
    private BigDecimal magnesiumMg;
    private BigDecimal vitaminDMcg;
    private BigDecimal calciumMg;
    private BigDecimal ironMg;
    private BigDecimal omega3G;
    private String suitabilityNotes;
    private String portionAdvice;
    private String contraindications;
    private String mealType;
    private String difficulty;
    private String costLevel;
    private String ingredients;
    private String instructions;
}
