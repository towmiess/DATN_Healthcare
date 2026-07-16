package com.javaweb.nutrition_service.repository;

import com.javaweb.nutrition_service.entity.IngredientEntity;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.Collection;
import java.util.List;
import java.util.Optional;

@Repository
public interface IngredientRepository extends JpaRepository<IngredientEntity, Long>, JpaSpecificationExecutor<IngredientEntity>, IngredientRepositoryCustom {
    Optional<IngredientEntity> findByNormalizedName(String normalizedName);

    List<IngredientEntity> findAllByNormalizedNameIn(Collection<String> normalizedNames);
}
