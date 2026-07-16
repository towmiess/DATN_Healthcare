package com.javaweb.nutrition_service.entity;

import jakarta.persistence.*;
import lombok.*;

import java.math.BigDecimal;

@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
@EqualsAndHashCode(onlyExplicitlyIncluded = true)
@Entity
@Table(name = "ingredient")
public class IngredientEntity {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @EqualsAndHashCode.Include
    private Long id;

    @Column(name = "food_name")
    private String foodName;

    @Column(name = "normalized_name")
    private String normalizedName;

    @Column(name = "calories", precision = 12, scale = 2)
    private BigDecimal calories;

    @Column(name = "protein", precision = 12, scale = 2)
    private BigDecimal protein;

    @Column(name = "fat", precision = 12, scale = 2)
    private BigDecimal fat;

    @Column(name = "carbs", precision = 12, scale = 2)
    private BigDecimal carbs;
}
