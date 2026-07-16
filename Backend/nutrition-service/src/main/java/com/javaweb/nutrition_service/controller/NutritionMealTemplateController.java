package com.javaweb.nutrition_service.controller;

import com.javaweb.nutrition_service.dto.response.MealRecommendationResponse;
import com.javaweb.nutrition_service.dto.request.NutritionMealTemplateAdminQueryRequest;
import com.javaweb.nutrition_service.dto.request.NutritionMealTemplateCreateRequest;
import com.javaweb.nutrition_service.dto.request.NutritionMealTemplateUpdateRequest;
import com.javaweb.nutrition_service.dto.response.NutritionMealTemplatePageResponse;
import com.javaweb.nutrition_service.entity.NutritionMealTemplateEntity;
import com.javaweb.nutrition_service.services.INutritionMealTemplateService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.ModelAttribute;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.LinkedHashMap;
import java.util.Map;

@RestController
@RequiredArgsConstructor
@RequestMapping("/api/nutrition/meal-templates")
public class NutritionMealTemplateController {

    private final INutritionMealTemplateService nutritionMealTemplateService;

    @GetMapping
    public ResponseEntity<NutritionMealTemplatePageResponse> getAdminMeals(@ModelAttribute NutritionMealTemplateAdminQueryRequest request) {
        return ResponseEntity.ok(nutritionMealTemplateService.getAdminMeals(request));
    }

    @PostMapping
    public ResponseEntity<Map<String, Object>> create(@Valid @RequestBody NutritionMealTemplateCreateRequest request) {
        NutritionMealTemplateEntity saved = nutritionMealTemplateService.create(request);

        Map<String, Object> response = new LinkedHashMap<>();
        response.put("message", "Meal template created successfully");
        response.put("id", saved.getId());
        response.put("name", saved.getName());

        return ResponseEntity.status(HttpStatus.CREATED).body(response);
    }

    @PostMapping("/batch")
    public ResponseEntity<Map<String, Object>> createBatch(@Valid @RequestBody List<NutritionMealTemplateCreateRequest> requests) {
        List<NutritionMealTemplateEntity> savedMeals = nutritionMealTemplateService.createAll(requests);

        Map<String, Object> response = new LinkedHashMap<>();
        response.put("message", "Meal templates created successfully");
        response.put("count", savedMeals.size());
        response.put(
                "ids",
                savedMeals.stream()
                        .map(NutritionMealTemplateEntity::getId)
                        .toList()
        );

        return ResponseEntity.status(HttpStatus.CREATED).body(response);
    }

    @PutMapping("/{id}")
    public ResponseEntity<Map<String, Object>> update(
            @PathVariable Long id,
            @RequestBody NutritionMealTemplateUpdateRequest request
    ) {
        NutritionMealTemplateEntity saved = nutritionMealTemplateService.update(id, request);

        Map<String, Object> response = new LinkedHashMap<>();
        response.put("message", "Meal template updated successfully");
        response.put("id", saved.getId());
        response.put("name", saved.getName());

        return ResponseEntity.ok(response);
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<Map<String, Object>> delete(@PathVariable Long id) {
        nutritionMealTemplateService.delete(id);

        Map<String, Object> response = new LinkedHashMap<>();
        response.put("message", "Meal template deleted successfully");
        response.put("id", id);

        return ResponseEntity.ok(response);
    }

    @GetMapping("/recommendations")
    public ResponseEntity<MealRecommendationResponse> recommendMeals() {
        return ResponseEntity.ok(nutritionMealTemplateService.recommendRandomMealsForCurrentUser());
    }
}
