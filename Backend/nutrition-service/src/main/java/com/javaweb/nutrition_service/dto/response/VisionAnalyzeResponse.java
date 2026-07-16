package com.javaweb.nutrition_service.dto.response;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;

@Getter
@Setter
@Builder
@NoArgsConstructor
@AllArgsConstructor
@JsonInclude(JsonInclude.Include.NON_NULL)
public class VisionAnalyzeResponse {

    @Builder.Default
    private String name = "";

    @Builder.Default
    private String image = "";

    @Builder.Default
    private BigDecimal totalCalories = BigDecimal.ZERO;

    @Builder.Default
    private BigDecimal totalProtein = BigDecimal.ZERO;

    @Builder.Default
    private BigDecimal totalFat = BigDecimal.ZERO;

    @Builder.Default
    private BigDecimal totalCarbs = BigDecimal.ZERO;

    @Builder.Default
    private List<VisionFoodItemResponse> detectedFoods = List.of();

    @Builder.Default
    private List<VisionIngredientMatchResponse> ingredientMatches = List.of();

    @JsonProperty("created_at")
    private Instant createdAt;
}
