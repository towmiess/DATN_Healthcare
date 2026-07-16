package com.javaweb.users_service.repository;

import com.javaweb.users_service.entity.UserEntity;
import com.javaweb.users_service.enums.UserStatus;
import com.javaweb.users_service.repository.custom.UserRepositoryCustom;
import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.time.Instant;
import java.util.Optional;

public interface UserRepository extends JpaRepository<UserEntity, Long>, UserRepositoryCustom {
    @EntityGraph(attributePaths = "roleEntities")
    @Query("select u from UserEntity u where u.id = :id and (u.deleted = false or u.deleted is null)")
    Optional<UserEntity> findByIdAndDeletedFalse(@Param("id") Long id);

    @Query("select count(u) from UserEntity u where u.deleted = false or u.deleted is null")
    long countByDeletedFalse();

    @Query("select count(u) from UserEntity u where u.status = :status and (u.deleted = false or u.deleted is null)")
    long countByStatusAndDeletedFalse(@Param("status") UserStatus status);

    @Query("select count(u) from UserEntity u where u.createdAt >= :from and (u.deleted = false or u.deleted is null)")
    long countRecentUsers(@Param("from") Instant from);
}
