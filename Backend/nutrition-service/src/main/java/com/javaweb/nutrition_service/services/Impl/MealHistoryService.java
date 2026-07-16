package com.javaweb.nutrition_service.services.Impl;

import com.javaweb.nutrition_service.dto.TokenPayload;
import com.javaweb.nutrition_service.dto.response.MealHistoryResponse;
import com.javaweb.nutrition_service.entity.MealHistoryEntity;
import com.javaweb.nutrition_service.repository.MealHistoryRepository;
import com.javaweb.nutrition_service.services.IMealHistoryService;
import com.javaweb.nutrition_service.util.CurrentTokenPayloadUtil;
import com.javaweb.nutrition_service.util.MealHistoryMapperUtil;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
@RequiredArgsConstructor
public class MealHistoryService implements IMealHistoryService {

    private final MealHistoryRepository mealHistoryRepository;
    private final CurrentTokenPayloadUtil currentTokenPayloadUtil;
    private final MealHistoryMapperUtil mealHistoryMapperUtil;

    @Transactional(readOnly = true)
    @Override
    public List<MealHistoryResponse> getCurrentUserMealHistory() {
        TokenPayload tokenPayload = currentTokenPayloadUtil.getCurrentTokenPayload();
        Long userId = tokenPayload.getUserId();

        List<MealHistoryEntity> histories = mealHistoryRepository.findAllByUserIdOrderByCreatedAtDesc(userId);
        return mealHistoryMapperUtil.toHistoryResponses(histories);
    }
}
