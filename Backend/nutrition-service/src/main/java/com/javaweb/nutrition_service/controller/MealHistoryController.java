package com.javaweb.nutrition_service.controller;

import com.javaweb.nutrition_service.dto.response.MealHistoryResponse;
import com.javaweb.nutrition_service.services.IMealHistoryService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequiredArgsConstructor
@RequestMapping("/api/meal-history")
public class MealHistoryController {

    private final IMealHistoryService mealHistoryService;

    @GetMapping
    public ResponseEntity<List<MealHistoryResponse>> getCurrentUserMealHistory() {
        return ResponseEntity.ok(mealHistoryService.getCurrentUserMealHistory());
    }
}
