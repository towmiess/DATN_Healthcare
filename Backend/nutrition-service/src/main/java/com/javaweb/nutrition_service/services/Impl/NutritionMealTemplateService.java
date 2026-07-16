package com.javaweb.nutrition_service.services.Impl;

import com.javaweb.nutrition_service.dto.request.NutritionMealTemplateAdminQueryRequest;
import com.javaweb.nutrition_service.dto.response.MealRecommendationResponse;
import com.javaweb.nutrition_service.dto.response.NutritionMealTemplatePageResponse;
import com.javaweb.nutrition_service.dto.response.NutritionMealTemplateResponse;
import com.javaweb.nutrition_service.dto.request.NutritionMealTemplateCreateRequest;
import com.javaweb.nutrition_service.dto.request.NutritionMealTemplateUpdateRequest;
import com.javaweb.nutrition_service.entity.NutritionMealTemplateEntity;
import com.javaweb.nutrition_service.repository.NutritionMealTemplateRepository;
import com.javaweb.nutrition_service.repository.NutritionUserTypeRepository;
import com.javaweb.nutrition_service.services.INutritionMealTemplateService;
import com.javaweb.nutrition_service.util.CurrentTokenPayloadUtil;
import com.javaweb.nutrition_service.util.NutritionMealTemplateAdminUtil;
import com.javaweb.nutrition_service.util.NutritionMealTemplateMapperUtil;
import com.javaweb.nutrition_service.util.NutritionMealTemplateResponseMapperUtil;
import com.javaweb.nutrition_service.util.NutritionMealTemplateUpdateMapperUtil;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

import java.util.List;

@Service
@RequiredArgsConstructor
public class NutritionMealTemplateService implements INutritionMealTemplateService {

    private final NutritionMealTemplateRepository nutritionMealTemplateRepository;
    private final NutritionUserTypeRepository nutritionUserTypeRepository;
    private final NutritionMealTemplateMapperUtil nutritionMealTemplateMapperUtil;
    private final NutritionMealTemplateResponseMapperUtil nutritionMealTemplateResponseMapperUtil;
    private final NutritionMealTemplateUpdateMapperUtil nutritionMealTemplateUpdateMapperUtil;
    private final NutritionMealTemplateAdminUtil nutritionMealTemplateAdminUtil;
    private final CurrentTokenPayloadUtil currentTokenPayloadUtil;

    @Transactional
    @Override
    public NutritionMealTemplateEntity create(NutritionMealTemplateCreateRequest request) {
        return nutritionMealTemplateRepository.save(nutritionMealTemplateMapperUtil.toEntity(request));
    }

    @Transactional
    @Override
    public List<NutritionMealTemplateEntity> createAll(List<NutritionMealTemplateCreateRequest> requests) {
        return nutritionMealTemplateRepository.saveAll(
                nutritionMealTemplateMapperUtil.toEntities(requests)
        );
    }

    @Transactional
    @Override
    public NutritionMealTemplateEntity update(Long id, NutritionMealTemplateUpdateRequest request) {
        NutritionMealTemplateEntity existing = nutritionMealTemplateRepository.findById(id)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Meal template not found"));

        nutritionMealTemplateUpdateMapperUtil.applyUpdate(existing, request);
        return nutritionMealTemplateRepository.save(existing);
    }

    @Transactional
    @Override
    public void delete(Long id) {
        if (!nutritionMealTemplateRepository.existsById(id)) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "Meal template not found");
        }
        nutritionMealTemplateRepository.deleteById(id);
    }

    @Transactional(readOnly = true)
    @Override
    public NutritionMealTemplatePageResponse getAdminMeals(NutritionMealTemplateAdminQueryRequest request) {
        Pageable pageable = nutritionMealTemplateAdminUtil.buildPageable(request.getPage(), request.getSize());
        Page<NutritionMealTemplateEntity> mealPage = nutritionMealTemplateRepository.findAdminMeals(
                nutritionMealTemplateAdminUtil.normalizeKeyword(request.getKeyword()),
                nutritionMealTemplateAdminUtil.normalizeMealType(request.getMealType()),
                pageable
        );

        List<NutritionMealTemplateResponse> items = nutritionMealTemplateResponseMapperUtil.toResponses(mealPage.getContent());

        return NutritionMealTemplatePageResponse.builder()
                .items(items)
                .page(mealPage.getNumber())
                .size(mealPage.getSize())
                .totalPages(mealPage.getTotalPages())
                .totalItems(mealPage.getTotalElements())
                .hasNext(mealPage.hasNext())
                .hasPrevious(mealPage.hasPrevious())
                .build();
    }

    @Transactional(readOnly = true)
    @Override
    public MealRecommendationResponse recommendRandomMealsForCurrentUser() {
        Long userId = currentTokenPayloadUtil.getCurrentTokenPayload().getUserId();
        List<String> rawUserTypes = nutritionUserTypeRepository.findTypeUsersByUserId(userId);
        List<NutritionMealTemplateEntity> meals = nutritionMealTemplateRepository.findRandomRecommendedMeals(
                rawUserTypes,
                6
        );
        List<NutritionMealTemplateResponse> mealResponses = nutritionMealTemplateResponseMapperUtil.toResponses(meals);

        return MealRecommendationResponse.builder()
                .userId(userId)
                .userTypes(rawUserTypes)
                .count(mealResponses.size())
                .meals(mealResponses)
                .build();
    }
}
