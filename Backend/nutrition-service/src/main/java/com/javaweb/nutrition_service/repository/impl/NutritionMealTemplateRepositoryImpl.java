package com.javaweb.nutrition_service.repository.impl;

import com.javaweb.nutrition_service.entity.NutritionMealTemplateEntity;
import com.javaweb.nutrition_service.repository.NutritionMealTemplateRepositoryCustom;
import com.javaweb.nutrition_service.util.NutritionMealTemplateQueryUtil;
import jakarta.persistence.EntityManager;
import jakarta.persistence.PersistenceContext;
import jakarta.persistence.Query;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageImpl;
import org.springframework.data.domain.Pageable;
import org.springframework.util.StringUtils;
import org.springframework.stereotype.Repository;

import java.util.HashMap;
import java.util.Locale;
import java.util.List;
import java.util.Map;
import java.util.Objects;

@Repository
@RequiredArgsConstructor
public class NutritionMealTemplateRepositoryImpl implements NutritionMealTemplateRepositoryCustom {

    @PersistenceContext
    private EntityManager entityManager;

    private final NutritionMealTemplateQueryUtil nutritionMealTemplateQueryUtil;

    @Override
    public List<NutritionMealTemplateEntity> findRandomRecommendedMeals(List<String> userTypes, int limit) {
        List<String> normalizedTypes = nutritionMealTemplateQueryUtil.normalizeUserTypes(userTypes);
        StringBuilder sql = new StringBuilder("select * from nutrition_meal_templates");

        List<String> conditions = normalizedTypes.stream()
                .map(nutritionMealTemplateQueryUtil::toCondition)
                .filter(Objects::nonNull)
                .toList();

        if (!conditions.isEmpty()) {
            sql.append(" where ").append(String.join(" and ", conditions));
        }

        sql.append(" order by random() limit :limit");

        Query query = entityManager.createNativeQuery(sql.toString(), NutritionMealTemplateEntity.class);
        query.setParameter("limit", limit);

        @SuppressWarnings("unchecked")
        List<NutritionMealTemplateEntity> meals = query.getResultList();
        return meals;
    }

    @Override
    public Page<NutritionMealTemplateEntity> findAdminMeals(String keyword, String mealType, Pageable pageable) {
        StringBuilder whereClause = new StringBuilder(" from nutrition_meal_templates nmte where 1=1");
        Map<String, Object> parameters = new HashMap<>();

        if (StringUtils.hasText(keyword)) {
            whereClause.append("""
                     and (
                        lower(cast(coalesce(nmte.name, '') as text)) like :keyword
                        or lower(cast(coalesce(nmte.category, '') as text)) like :keyword
                        or lower(cast(coalesce(nmte.cuisine, '') as text)) like :keyword
                    )
                    """);
            parameters.put("keyword", "%" + keyword.trim().toLowerCase(Locale.ROOT) + "%");
        }

        if (StringUtils.hasText(mealType)) {
            whereClause.append("""
                     and lower(cast(coalesce(nmte.meal_type, '') as text)) like :mealType
                    """);
            parameters.put("mealType", "%" + mealType.trim().toLowerCase(Locale.ROOT) + "%");
        }

        String dataSql = "select *" + whereClause + " order by nmte.id desc";
        String countSql = "select count(*)" + whereClause;

        Query dataQuery = entityManager.createNativeQuery(dataSql, NutritionMealTemplateEntity.class);
        Query countQuery = entityManager.createNativeQuery(countSql);

        parameters.forEach((key, value) -> {
            dataQuery.setParameter(key, value);
            countQuery.setParameter(key, value);
        });

        dataQuery.setFirstResult((int) pageable.getOffset());
        dataQuery.setMaxResults(pageable.getPageSize());

        @SuppressWarnings("unchecked")
        List<NutritionMealTemplateEntity> meals = dataQuery.getResultList();
        Number totalElements = (Number) countQuery.getSingleResult();

        return new PageImpl<>(meals, pageable, totalElements == null ? 0L : totalElements.longValue());
    }
}
