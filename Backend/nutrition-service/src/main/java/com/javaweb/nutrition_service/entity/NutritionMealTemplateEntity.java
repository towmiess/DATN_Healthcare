package com.javaweb.nutrition_service.entity;

import com.fasterxml.jackson.annotation.JsonIgnore;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.JoinTable;
import jakarta.persistence.ManyToMany;
import jakarta.persistence.Table;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Builder.Default;
import lombok.EqualsAndHashCode;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.math.BigDecimal;
import java.util.LinkedHashSet;
import java.util.Set;

@Getter
@Setter
@Builder
@NoArgsConstructor
@AllArgsConstructor
@EqualsAndHashCode(onlyExplicitlyIncluded = true)
@Entity
@Table(name = "nutrition_meal_templates")
public class NutritionMealTemplateEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @EqualsAndHashCode.Include
    private Long id;

    @Column(name = "name", nullable = false, length = 255)
    private String name;

    @Column(name = "category", columnDefinition = "text")
    private String category;

    @Column(name = "cuisine", columnDefinition = "text")
    private String cuisine;

    @Column(name = "keywords", columnDefinition = "text")
    private String keywords;

    @Column(name = "description", columnDefinition = "text")
    private String description;

    @Column(name = "prep_time", length = 50)
    private String prepTime;

    @Column(name = "cook_time", length = 50)
    private String cookTime;

    @Column(name = "total_time", length = 50)
    private String totalTime;

    @Column(name = "servings")
    private Integer servings;

    @Column(name = "serving_size", length = 120)
    private String servingSize;

    @Column(name = "glycemic_index", length = 40)
    private String glycemicIndex;

    @Column(name = "glycemic_load", precision = 10, scale = 2)
    private BigDecimal glycemicLoad;

    @Column(name = "calories")
    private Integer calories;

    @Column(name = "total_fat_g", precision = 10, scale = 2)
    private BigDecimal totalFatG;

    @Column(name = "saturated_fat_g", precision = 10, scale = 2)
    private BigDecimal saturatedFatG;

    @Column(name = "trans_fat_g", precision = 10, scale = 2)
    private BigDecimal transFatG;

    @Column(name = "cholesterol_mg", precision = 10, scale = 2)
    private BigDecimal cholesterolMg;

    @Column(name = "sodium_mg", precision = 10, scale = 2)
    private BigDecimal sodiumMg;

    @Column(name = "total_carbohydrate_g", precision = 10, scale = 2)
    private BigDecimal totalCarbohydrateG;

    @Column(name = "dietary_fiber_g", precision = 10, scale = 2)
    private BigDecimal dietaryFiberG;

    @Column(name = "sugars_g", precision = 10, scale = 2)
    private BigDecimal sugarsG;

    @Column(name = "added_sugars_g", precision = 10, scale = 2)
    private BigDecimal addedSugarsG;

    @Column(name = "protein_g", precision = 10, scale = 2)
    private BigDecimal proteinG;

    @Column(name = "potassium_mg", precision = 10, scale = 2)
    private BigDecimal potassiumMg;

    @Column(name = "phosphorus_mg", precision = 10, scale = 2)
    private BigDecimal phosphorusMg;

    @Column(name = "magnesium_mg", precision = 10, scale = 2)
    private BigDecimal magnesiumMg;

    @Column(name = "vitamin_d_mcg", precision = 10, scale = 2)
    private BigDecimal vitaminDMcg;

    @Column(name = "calcium_mg", precision = 10, scale = 2)
    private BigDecimal calciumMg;

    @Column(name = "iron_mg", precision = 10, scale = 2)
    private BigDecimal ironMg;

    @Column(name = "omega3_g", precision = 10, scale = 2)
    private BigDecimal omega3G;

    @Column(name = "suitable_type1", nullable = false)
    private boolean suitableType1;

    @Column(name = "suitable_type2", nullable = false)
    private boolean suitableType2;

    @Column(name = "suitable_gestational", nullable = false)
    private boolean suitableGestational;

    @Column(name = "suitable_neuropathy", nullable = false)
    private boolean suitableNeuropathy;

    @Column(name = "suitable_cardiovascular", nullable = false)
    private boolean suitableCardiovascular;

    @Column(name = "suitable_stroke", nullable = false)
    private boolean suitableStroke;

    @Column(name = "suitability_notes", columnDefinition = "text")
    private String suitabilityNotes;

    @Column(name = "portion_advice", columnDefinition = "text")
    private String portionAdvice;

    @Column(name = "contraindications", columnDefinition = "text")
    private String contraindications;

    @Column(name = "meal_type", columnDefinition = "text")
    private String mealType;

    @Column(name = "difficulty", length = 50)
    private String difficulty;

    @Column(name = "cost_level", length = 50)
    private String costLevel;

    @Column(name = "ingredients", columnDefinition = "text")
    private String ingredients;

    @Column(name = "instructions", columnDefinition = "text")
    private String instructions;

    @Default
    @ManyToMany
    @JoinTable(
            name = "nutrition_meal_template_user_types",
            joinColumns = @JoinColumn(name = "meal_template_id"),
            inverseJoinColumns = @JoinColumn(name = "user_type_id")
    )
    @JsonIgnore
    private Set<NutritionUserTypeEntity> userTypes = new LinkedHashSet<>();
}
