package com.javaweb.nutrition_service.services.Impl;

import com.javaweb.nutrition_service.dto.request.IngredientCreateRequest;
import com.javaweb.nutrition_service.dto.request.IngredientAdminQueryRequest;
import com.javaweb.nutrition_service.dto.request.IngredientUpdateRequest;
import com.javaweb.nutrition_service.dto.response.IngredientResponse;
import com.javaweb.nutrition_service.dto.response.IngredientPageResponse;
import com.javaweb.nutrition_service.entity.IngredientEntity;
import com.javaweb.nutrition_service.repository.IngredientRepository;
import com.javaweb.nutrition_service.services.IIngredientService;
import com.javaweb.nutrition_service.util.IngredientMapperUtil;
import com.javaweb.nutrition_service.util.IngredientUpdateMapperUtil;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.http.HttpStatus;
import org.springframework.data.jpa.domain.Specification;
import org.springframework.util.StringUtils;

import jakarta.persistence.criteria.Predicate;
import java.util.List;
import java.util.ArrayList;
import java.util.Locale;

@Service
@RequiredArgsConstructor
public class IngredientService implements IIngredientService {

    private final IngredientRepository ingredientRepository;
    private final IngredientMapperUtil ingredientMapperUtil;
    private final IngredientUpdateMapperUtil ingredientUpdateMapperUtil;

    @Transactional
    @Override
    public IngredientResponse create(IngredientCreateRequest request) {
        IngredientEntity saved = ingredientRepository.save(ingredientMapperUtil.toEntity(request));
        return ingredientMapperUtil.toResponse(saved);
    }

    @Transactional
    @Override
    public List<IngredientResponse> createAll(List<IngredientCreateRequest> requests) {
        if (requests == null || requests.isEmpty()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "At least one ingredient is required");
        }

        List<IngredientEntity> entities = ingredientMapperUtil.toEntities(requests);

        return ingredientRepository.saveAll(entities)
                .stream()
                .map(ingredientMapperUtil::toResponse)
                .toList();
    }

    @Transactional
    @Override
    public IngredientResponse update(Long id, IngredientUpdateRequest request) {
        IngredientEntity existing = ingredientRepository.findById(id)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Ingredient not found"));
        ingredientUpdateMapperUtil.applyUpdate(existing, request);
        return ingredientMapperUtil.toResponse(ingredientRepository.save(existing));
    }

    @Transactional
    @Override
    public void delete(Long id) {
        if (!ingredientRepository.existsById(id)) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "Ingredient not found");
        }
        ingredientRepository.deleteById(id);
    }

    @Transactional(readOnly = true)
    @Override
    public IngredientPageResponse getAdminIngredients(IngredientAdminQueryRequest request) {
        int page = request.getPage() == null || request.getPage() < 0 ? 0 : request.getPage();
        int size = request.getSize() == null || request.getSize() <= 0 ? 10 : request.getSize();
        String keyword = StringUtils.hasText(request.getKeyword()) ? request.getKeyword().trim().toLowerCase(Locale.ROOT) : null;

        Pageable pageable = PageRequest.of(page, size, Sort.by(Sort.Direction.DESC, "id"));

        Specification<IngredientEntity> specification = (root, query, cb) -> {
            if (!StringUtils.hasText(keyword)) {
                return cb.conjunction();
            }

            String like = "%" + keyword + "%";
            List<Predicate> predicates = new ArrayList<>();
            predicates.add(cb.like(cb.lower(root.get("foodName")), like));
            predicates.add(cb.like(cb.lower(root.get("normalizedName")), like));
            return cb.or(predicates.toArray(Predicate[]::new));
        };

        Page<IngredientEntity> pageResult = ingredientRepository.findAll(specification, pageable);
        List<IngredientResponse> items = ingredientMapperUtil.toResponses(pageResult.getContent());

        return IngredientPageResponse.builder()
                .items(items)
                .page(pageResult.getNumber())
                .size(pageResult.getSize())
                .totalPages(pageResult.getTotalPages())
                .totalItems(pageResult.getTotalElements())
                .hasNext(pageResult.hasNext())
                .hasPrevious(pageResult.hasPrevious())
                .build();
    }
}
