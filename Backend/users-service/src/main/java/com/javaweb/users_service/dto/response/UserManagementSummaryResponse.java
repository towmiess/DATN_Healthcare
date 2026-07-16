package com.javaweb.users_service.dto.response;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Getter
@Setter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class UserManagementSummaryResponse {
    private Long totalUsers;
    private Long activeUsers;
    private Long blockedUsers;
    private Long recentUsers;
}
