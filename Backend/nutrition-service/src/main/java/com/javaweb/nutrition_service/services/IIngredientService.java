package com.javaweb.nutrition_service.services;

import com.javaweb.nutrition_service.dto.request.IngredientCreateRequest;
import com.javaweb.nutrition_service.dto.request.IngredientAdminQueryRequest;
import com.javaweb.nutrition_service.dto.request.IngredientUpdateRequest;
import com.javaweb.nutrition_service.dto.response.IngredientResponse;
import com.javaweb.nutrition_service.dto.response.IngredientPageResponse;

import java.util.List;

public interface IIngredientService {
    IngredientResponse create(IngredientCreateRequest request);

    List<IngredientResponse> createAll(List<IngredientCreateRequest> requests);

    IngredientResponse update(Long id, IngredientUpdateRequest request);

    void delete(Long id);

    IngredientPageResponse getAdminIngredients(IngredientAdminQueryRequest request);
}
