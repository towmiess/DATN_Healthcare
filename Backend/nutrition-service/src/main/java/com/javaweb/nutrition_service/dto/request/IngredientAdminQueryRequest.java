package com.javaweb.nutrition_service.dto.request;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Getter
@Setter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class IngredientAdminQueryRequest {
    private Integer page;
    private Integer size;
    private String keyword;
}
