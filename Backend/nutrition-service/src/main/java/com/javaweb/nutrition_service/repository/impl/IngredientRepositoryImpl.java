package com.javaweb.nutrition_service.repository.impl;

import com.javaweb.nutrition_service.entity.IngredientEntity;
import com.javaweb.nutrition_service.repository.IngredientRepositoryCustom;
import jakarta.persistence.EntityManager;
import jakarta.persistence.PersistenceContext;
import jakarta.persistence.Query;
import org.springframework.stereotype.Repository;
import org.springframework.util.StringUtils;

import java.util.List;

@Repository
public class IngredientRepositoryImpl implements IngredientRepositoryCustom {

    @PersistenceContext
    private EntityManager entityManager;

    @Override
    public List<IngredientEntity> searchCandidates(
            String exactFoodName,
            String exactNormalizedName,
            String foodNamePrefix,
            String normalizedNamePrefix,
            String foodNameContains,
            String normalizedNameContains,
            int limit
    ) {
        if (limit <= 0) {
            return List.of();
        }

        StringBuilder sql = new StringBuilder("""
                select *
                from ingredient
                where lower(food_name) = :exactFoodName
                   or lower(normalized_name) = :exactNormalizedName
                   or lower(food_name) like :foodNamePrefix escape '\\'
                   or lower(normalized_name) like :normalizedNamePrefix escape '\\'
                   or lower(food_name) like :foodNameContains escape '\\'
                   or lower(normalized_name) like :normalizedNameContains escape '\\'
                order by
                    case
                        when lower(food_name) = :exactFoodName then 0
                        when lower(normalized_name) = :exactNormalizedName then 1
                        when lower(food_name) like :foodNamePrefix escape '\\' then 2
                        when lower(normalized_name) like :normalizedNamePrefix escape '\\' then 3
                        when lower(food_name) like :foodNameContains escape '\\' then 4
                        when lower(normalized_name) like :normalizedNameContains escape '\\' then 5
                        else 6
                    end,
                    id
                """);

        Query query = entityManager.createNativeQuery(sql.toString(), IngredientEntity.class);
        query.setParameter("exactFoodName", normalizeSqlValue(exactFoodName));
        query.setParameter("exactNormalizedName", normalizeSqlValue(exactNormalizedName));
        query.setParameter("foodNamePrefix", normalizeSqlValue(foodNamePrefix));
        query.setParameter("normalizedNamePrefix", normalizeSqlValue(normalizedNamePrefix));
        query.setParameter("foodNameContains", normalizeSqlValue(foodNameContains));
        query.setParameter("normalizedNameContains", normalizeSqlValue(normalizedNameContains));
        query.setMaxResults(limit);

        @SuppressWarnings("unchecked")
        List<IngredientEntity> candidates = query.getResultList();
        return candidates;
    }

    private String normalizeSqlValue(String value) {
        return StringUtils.hasText(value) ? value.trim().toLowerCase() : "";
    }
}
