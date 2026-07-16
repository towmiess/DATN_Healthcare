package com.javaweb.nutrition_service.repository;

import com.javaweb.nutrition_service.entity.MealHistoryEntity;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface MealHistoryRepository extends JpaRepository<MealHistoryEntity, Long> {

    List<MealHistoryEntity> findAllByUserIdOrderByCreatedAtDesc(Long userId);
}
