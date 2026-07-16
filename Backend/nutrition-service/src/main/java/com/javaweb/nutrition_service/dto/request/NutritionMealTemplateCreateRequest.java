package com.javaweb.nutrition_service.dto.request;

import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;
import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.constraints.NotBlank;
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
public class NutritionMealTemplateCreateRequest {

    @NotBlank
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
    @JsonProperty("vitamin_d_mcg")
    private BigDecimal vitaminDMcg;
    private BigDecimal calciumMg;
    private BigDecimal ironMg;
    private BigDecimal omega3G;
    private boolean suitableType1;
    private boolean suitableType2;
    private boolean suitableGestational;
    private boolean suitableNeuropathy;
    private boolean suitableCardiovascular;
    private boolean suitableStroke;
    private String suitabilityNotes;
    private String portionAdvice;
    private String contraindications;
    private String mealType;
    private String difficulty;
    private String costLevel;
    private String ingredients;
    private String instructions;
}
