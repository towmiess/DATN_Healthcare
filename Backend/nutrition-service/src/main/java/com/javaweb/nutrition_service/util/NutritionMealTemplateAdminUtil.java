package com.javaweb.nutrition_service.util;

import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Component;

@Component
public class NutritionMealTemplateAdminUtil {

    private static final int DEFAULT_PAGE = 0;
    private static final int DEFAULT_SIZE = 8;
    private static final int MAX_SIZE = 50;

    public Pageable buildPageable(Integer page, Integer size) {
        return PageRequest.of(
                normalizePage(page),
                normalizeSize(size),
                Sort.by(Sort.Direction.DESC, "id")
        );
    }

    public String normalizeKeyword(String value) {
        return trimToNull(value);
    }

    public String normalizeMealType(String value) {
        return trimToNull(value);
    }

    private int normalizePage(Integer page) {
        if (page == null || page < 0) {
            return DEFAULT_PAGE;
        }
        return page;
    }

    private int normalizeSize(Integer size) {
        if (size == null || size <= 0) {
            return DEFAULT_SIZE;
        }
        return Math.min(size, MAX_SIZE);
    }

    private String trimToNull(String value) {
        if (value == null) {
            return null;
        }
        String trimmed = value.trim();
        return trimmed.isEmpty() ? null : trimmed;
    }
}
