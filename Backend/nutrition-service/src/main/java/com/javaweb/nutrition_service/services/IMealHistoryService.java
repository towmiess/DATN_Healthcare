package com.javaweb.nutrition_service.services;

import com.javaweb.nutrition_service.dto.response.MealHistoryResponse;

import java.util.List;

public interface IMealHistoryService {

    List<MealHistoryResponse> getCurrentUserMealHistory();
}
