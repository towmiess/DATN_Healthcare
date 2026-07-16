package com.javaweb.nutrition_service.util;

import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;

import java.util.Locale;

@Component
@RequiredArgsConstructor
public class IngredientSearchUtil {

    private final IngredientMapperUtil ingredientMapperUtil;

    public SearchTerms buildSearchTerms(String foodName) {
        String displayName = ingredientMapperUtil.normalizeDisplayName(foodName);
        String exactFoodName = displayName.toLowerCase(Locale.ROOT);
        String normalizedName = ingredientMapperUtil.normalizeKey(displayName);

        return new SearchTerms(
                exactFoodName,
                normalizedName,
                toLikePrefix(exactFoodName),
                toLikeContains(exactFoodName),
                toLikePrefix(normalizedName),
                toLikeContains(normalizedName)
        );
    }

    public String normalizeComparisonKey(String value) {
        return ingredientMapperUtil.normalizeKey(value);
    }

    public String normalizeDisplayLower(String value) {
        return ingredientMapperUtil.normalizeDisplayName(value).toLowerCase(Locale.ROOT);
    }

    public String toLikePrefix(String value) {
        return escapeLike(value) + "%";
    }

    public String toLikeContains(String value) {
        return "%" + escapeLike(value) + "%";
    }

    public double levenshteinSimilarity(String left, String right) {
        String normalizedLeft = StringUtils.hasText(left) ? left.trim() : "";
        String normalizedRight = StringUtils.hasText(right) ? right.trim() : "";

        if (!StringUtils.hasText(normalizedLeft) && !StringUtils.hasText(normalizedRight)) {
            return 1.0d;
        }
        if (!StringUtils.hasText(normalizedLeft) || !StringUtils.hasText(normalizedRight)) {
            return 0.0d;
        }

        int distance = levenshteinDistance(normalizedLeft, normalizedRight);
        int maxLength = Math.max(normalizedLeft.length(), normalizedRight.length());
        if (maxLength == 0) {
            return 1.0d;
        }
        return 1.0d - ((double) distance / (double) maxLength);
    }

    private String escapeLike(String value) {
        if (!StringUtils.hasText(value)) {
            return "";
        }

        return value
                .replace("\\", "\\\\")
                .replace("%", "\\%")
                .replace("_", "\\_");
    }

    private int levenshteinDistance(String left, String right) {
        int leftLength = left.length();
        int rightLength = right.length();

        int[] previous = new int[rightLength + 1];
        int[] current = new int[rightLength + 1];

        for (int j = 0; j <= rightLength; j++) {
            previous[j] = j;
        }

        for (int i = 1; i <= leftLength; i++) {
            current[0] = i;
            char leftChar = left.charAt(i - 1);

            for (int j = 1; j <= rightLength; j++) {
                int substitutionCost = leftChar == right.charAt(j - 1) ? 0 : 1;
                current[j] = Math.min(
                        Math.min(current[j - 1] + 1, previous[j] + 1),
                        previous[j - 1] + substitutionCost
                );
            }

            int[] swap = previous;
            previous = current;
            current = swap;
        }

        return previous[rightLength];
    }

    public record SearchTerms(
            String exactFoodName,
            String exactNormalizedName,
            String foodNamePrefix,
            String foodNameContains,
            String normalizedNamePrefix,
            String normalizedNameContains
    ) {
    }
}
