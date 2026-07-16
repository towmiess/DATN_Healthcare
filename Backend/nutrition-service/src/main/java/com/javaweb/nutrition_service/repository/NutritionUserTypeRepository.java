package com.javaweb.nutrition_service.repository;

import com.javaweb.nutrition_service.entity.NutritionUserTypeEntity;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface NutritionUserTypeRepository extends JpaRepository<NutritionUserTypeEntity, Long> {

    @Query(value = """
            select nut.type_user
            from users_nutrition_user_types unt
            join nutrition_user_types nut on nut.id = unt.user_type_id
            where unt.user_id = :userId
            """, nativeQuery = true)
    List<String> findTypeUsersByUserId(@Param("userId") Long userId);
}
