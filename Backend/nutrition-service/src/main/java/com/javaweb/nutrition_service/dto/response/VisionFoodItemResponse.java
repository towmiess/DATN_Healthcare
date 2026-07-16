package com.javaweb.nutrition_service.dto.response;

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
public class VisionFoodItemResponse {

    private String foodName;
    private Integer weightGram;
    private BigDecimal caloriesPer100Gram;
    private BigDecimal proteinPer100Gram;
    private BigDecimal fatPer100Gram;
    private BigDecimal carbsPer100Gram;
}
