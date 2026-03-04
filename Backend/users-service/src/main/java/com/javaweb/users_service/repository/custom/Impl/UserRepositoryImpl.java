package com.javaweb.users_service.repository.custom.Impl;

import com.javaweb.users_service.dto.request.GetAllUserRequest;
import com.javaweb.users_service.repository.custom.UserRepositoryCustom;
import com.javaweb.users_service.util.HastextUtil;
import com.javaweb.users_service.util.QueryKeywordUtil;
import jakarta.persistence.EntityManager;
import jakarta.persistence.PersistenceContext;
import jakarta.persistence.Query;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
@RequiredArgsConstructor
public class UserRepositoryImpl implements UserRepositoryCustom {
    @PersistenceContext
    private EntityManager entityManager;

    private final QueryKeywordUtil queryKeywordUtil;
    private final HastextUtil hastextUtil;

    private void queryNomal(GetAllUserRequest request, StringBuilder where){
        if(request.getStatus() != null){
            where.append(" AND u.status = :status");
        }
        if(request.getLastId() != null){
            where.append(" AND u.id > :lastId");
        }
        String keywordCondition = queryKeywordUtil.buildKeywordCondition(request);

        if (!keywordCondition.isEmpty()) {
            where.append(" AND (");
            where.append(keywordCondition);
            where.append(")");
        }

        where.append(" ORDER BY u.id ASC ");

        if(request.getSize() != null){
            where.append(" LIMIT :size ");
        }
    }
    @Override
    public List<Object[]> findAllUsers(GetAllUserRequest request) {
        StringBuilder sql = new StringBuilder("SELECT u.id, u.full_name, u.email, u.phone_number, u.username, u.avatar, u.status FROM users u ");
        StringBuilder where = new StringBuilder(" WHERE 1 = 1 AND deleted = false ");
        queryNomal(request, where);
        sql.append(where);

        Query query = entityManager.createNativeQuery(sql.toString());
        if(request.getStatus() != null){
            query.setParameter("status", request.getStatus());
        }
        if(request.getLastId() != null){
            query.setParameter("lastId", request.getLastId());
        }
        if(hastextUtil.hasText(request.getUsername())){
            query.setParameter("username","%" + request.getUsername().trim() + "%");
        }
        if(hastextUtil.hasText(request.getPhoneNumber())){
            query.setParameter("phoneNumber", "%" + request.getPhoneNumber().trim() + "%");
        }
        if(hastextUtil.hasText(request.getFullName())){
            query.setParameter("fullName", "%" + request.getFullName().trim() + "%");
        }
        if (request.getSize() != null) {
            query.setParameter("size", request.getSize());
        }
        return query.getResultList();
    }
}
