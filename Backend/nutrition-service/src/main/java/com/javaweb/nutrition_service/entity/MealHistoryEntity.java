package com.javaweb.nutrition_service.entity;

import jakarta.persistence.*;
import lombok.*;
import org.hibernate.annotations.CreationTimestamp;
import org.hibernate.annotations.UpdateTimestamp;

import java.math.BigDecimal;
import java.time.Instant;

@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
@EqualsAndHashCode(onlyExplicitlyIncluded = true)
@Entity
@Table(name = "meal_history")
public class MealHistoryEntity {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @EqualsAndHashCode.Include
    private Long id;

    @Column(nullable = false, name = "user_id")
    private Long userId;

    @Column(name = "image")
    private String image;

    @Column(name = "name")
    private String name;

    @Column(name = "total_calories", precision = 12, scale = 2)
    private BigDecimal totalCalories;

    @Column(name = "total_protein", precision = 12, scale = 2)
    private BigDecimal totalProtein;

    @Column(name = "total_fat", precision = 12, scale = 2)
    private BigDecimal totalFat;

    @Column(name = "total_carbs", precision = 12, scale = 2)
    private BigDecimal totalCarbs;

    @CreationTimestamp
    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    @UpdateTimestamp
    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt;
}
