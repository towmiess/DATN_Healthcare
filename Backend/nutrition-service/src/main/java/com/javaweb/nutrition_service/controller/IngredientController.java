package com.javaweb.nutrition_service.controller;

import com.javaweb.nutrition_service.dto.request.IngredientCreateRequest;
import com.javaweb.nutrition_service.dto.request.IngredientAdminQueryRequest;
import com.javaweb.nutrition_service.dto.request.IngredientUpdateRequest;
import com.javaweb.nutrition_service.dto.response.IngredientPageResponse;
import com.javaweb.nutrition_service.dto.response.IngredientResponse;
import com.javaweb.nutrition_service.services.IIngredientService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.ModelAttribute;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@RestController
@RequiredArgsConstructor
@RequestMapping("/api/nutrition/ingredients")
public class IngredientController {

    private final IIngredientService ingredientService;

    @GetMapping
    public ResponseEntity<IngredientPageResponse> getAdminIngredients(@ModelAttribute IngredientAdminQueryRequest request) {
        return ResponseEntity.ok(ingredientService.getAdminIngredients(request));
    }

    @PostMapping
    public ResponseEntity<Map<String, Object>> create(@Valid @RequestBody IngredientCreateRequest request) {
        IngredientResponse saved = ingredientService.create(request);

        Map<String, Object> response = new LinkedHashMap<>();
        response.put("message", "Ingredient created successfully");
        response.put("ingredient", saved);

        return ResponseEntity.status(HttpStatus.CREATED).body(response);
    }

    @PostMapping("/batch")
    public ResponseEntity<Map<String, Object>> createBatch(@Valid @RequestBody List<@Valid IngredientCreateRequest> requests) {
        List<IngredientResponse> savedIngredients = ingredientService.createAll(requests);

        Map<String, Object> response = new LinkedHashMap<>();
        response.put("message", "Ingredients created successfully");
        response.put("count", savedIngredients.size());
        response.put("ingredients", savedIngredients);

        return ResponseEntity.status(HttpStatus.CREATED).body(response);
    }

    @PutMapping("/{id}")
    public ResponseEntity<Map<String, Object>> update(
            @PathVariable Long id,
            @RequestBody IngredientUpdateRequest request
    ) {
        IngredientResponse saved = ingredientService.update(id, request);

        Map<String, Object> response = new LinkedHashMap<>();
        response.put("message", "Ingredient updated successfully");
        response.put("ingredient", saved);

        return ResponseEntity.ok(response);
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<Map<String, Object>> delete(@PathVariable Long id) {
        ingredientService.delete(id);

        Map<String, Object> response = new LinkedHashMap<>();
        response.put("message", "Ingredient deleted successfully");
        response.put("id", id);

        return ResponseEntity.ok(response);
    }
}
