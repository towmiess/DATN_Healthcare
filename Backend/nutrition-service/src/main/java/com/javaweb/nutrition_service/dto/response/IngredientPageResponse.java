package com.javaweb.nutrition_service.dto.response;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.util.List;

@Getter
@Setter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class IngredientPageResponse {
    private List<IngredientResponse> items;
    private Integer page;
    private Integer size;
    private Integer totalPages;
    private Long totalItems;
    private Boolean hasNext;
    private Boolean hasPrevious;
}
