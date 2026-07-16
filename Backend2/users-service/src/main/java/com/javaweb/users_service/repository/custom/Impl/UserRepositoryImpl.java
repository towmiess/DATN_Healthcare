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

    }
    @Override
    public List<Object[]> findAllUsers(GetAllUserRequest request) {
        StringBuilder sql = new StringBuilder("""
                SELECT u.id,
                       u.full_name,
                       u.email,
                       u.phone_number,
                       u.avatar,
                       u.status,
                       COALESCE(string_agg(DISTINCT r.name, ','), '') AS roles,
                       u.created_at,
                       u.updated_at
                FROM users u
                LEFT JOIN users_roles ur ON ur.user_id = u.id
                LEFT JOIN roles r ON r.id = ur.role_id
                """);
        StringBuilder where = new StringBuilder(" WHERE 1 = 1 AND COALESCE(u.deleted, false) = false ");
        queryNomal(request, where);
        where.append(" GROUP BY u.id, u.full_name, u.email, u.phone_number, u.avatar, u.status, u.created_at, u.updated_at ");
        where.append(" ORDER BY u.id ASC ");
        if(request.getSize() != null){
            where.append(" LIMIT :size ");
        }
        sql.append(where);

        Query query = entityManager.createNativeQuery(sql.toString());
        if(request.getStatus() != null){
            query.setParameter("status", request.getStatus());
        }
        if(request.getLastId() != null){
            query.setParameter("lastId", request.getLastId());
        }
        if(hastextUtil.hasText(request.getEmail())){
            query.setParameter("email","%" + request.getEmail().trim() + "%");
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
