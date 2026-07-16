package com.javaweb.nutrition_service.dto.response;

import com.fasterxml.jackson.annotation.JsonInclude;
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
@JsonInclude(JsonInclude.Include.NON_NULL)
public class VisionIngredientMatchResponse {

    private String sourceFoodName;
    private Integer inputWeightGram;

    private Boolean matched;

    private Long matchedIngredientId;
    private String matchedFoodName;
    private String matchedNormalizedName;

    private BigDecimal caloriesPer100Gram;
    private BigDecimal proteinPer100Gram;
    private BigDecimal fatPer100Gram;
    private BigDecimal carbsPer100Gram;

    private Double similarity;
}
