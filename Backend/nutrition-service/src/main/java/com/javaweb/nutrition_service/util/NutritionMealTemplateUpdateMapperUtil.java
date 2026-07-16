package com.javaweb.nutrition_service.util;

import com.javaweb.nutrition_service.dto.request.NutritionMealTemplateUpdateRequest;
import com.javaweb.nutrition_service.entity.NutritionMealTemplateEntity;
import org.springframework.beans.BeanUtils;
import org.springframework.stereotype.Component;

import java.beans.PropertyDescriptor;
import java.util.HashSet;
import java.util.Set;

@Component
public class NutritionMealTemplateUpdateMapperUtil {

    public void applyUpdate(NutritionMealTemplateEntity target, NutritionMealTemplateUpdateRequest request) {
        if (target == null || request == null) {
            return;
        }

        BeanUtils.copyProperties(request, target, getNullPropertyNames(request));
    }

    private String[] getNullPropertyNames(Object source) {
        PropertyDescriptor[] propertyDescriptors = BeanUtils.getPropertyDescriptors(source.getClass());
        Set<String> emptyNames = new HashSet<>();

        for (PropertyDescriptor descriptor : propertyDescriptors) {
            try {
                if (descriptor.getReadMethod() == null) {
                    continue;
                }
                Object value = descriptor.getReadMethod().invoke(source);
                if (value == null) {
                    emptyNames.add(descriptor.getName());
                }
            } catch (Exception ignored) {
                emptyNames.add(descriptor.getName());
            }
        }

        emptyNames.add("class");
        return emptyNames.toArray(String[]::new);
    }
}
