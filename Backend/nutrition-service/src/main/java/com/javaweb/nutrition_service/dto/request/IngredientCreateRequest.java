package com.javaweb.nutrition_service.dto.request;

import jakarta.validation.constraints.DecimalMin;
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
public class IngredientCreateRequest {

    @NotBlank
    private String foodName;

    private String normalizedName;

    @DecimalMin(value = "0.0", inclusive = true)
    private BigDecimal calories;

    @DecimalMin(value = "0.0", inclusive = true)
    private BigDecimal protein;

    @DecimalMin(value = "0.0", inclusive = true)
    private BigDecimal fat;

    @DecimalMin(value = "0.0", inclusive = true)
    private BigDecimal carbs;
}
