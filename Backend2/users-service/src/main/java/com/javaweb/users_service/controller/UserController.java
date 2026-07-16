package com.javaweb.users_service.controller;

import com.javaweb.users_service.dto.request.UpdateUserRequest;
import com.javaweb.users_service.dto.request.UpdateUserStatusRequest;
import com.javaweb.users_service.dto.response.BaseResponse;
import com.javaweb.users_service.dto.response.UserManagementSummaryResponse;
import com.javaweb.users_service.dto.response.UserResponse;
import com.javaweb.users_service.services.IUserServices;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

@RestController
@RequiredArgsConstructor
@RequestMapping("/api/users")
public class UserController {

    private final IUserServices userService;

    @GetMapping
    public ResponseEntity<BaseResponse<List<UserResponse>>> getAllUsers(@RequestParam Map<String, Object> params) {
        return ResponseEntity.ok(userService.getAllUsers(params));
    }

    @GetMapping("/summary")
    public ResponseEntity<BaseResponse<UserManagementSummaryResponse>> getSummary() {
        return ResponseEntity.ok(userService.getSummary());
    }

    @GetMapping("/{id}")
    public ResponseEntity<BaseResponse<UserResponse>> getUserById(@PathVariable Long id) {
        return ResponseEntity.ok(userService.getUserById(id));
    }

    @PutMapping("/{id}")
    public ResponseEntity<BaseResponse<UserResponse>> updateUser(
            @PathVariable Long id,
            @RequestBody UpdateUserRequest request
    ) {
        return ResponseEntity.ok(userService.updateUser(id, request));
    }

    @PatchMapping("/{id}/status")
    public ResponseEntity<BaseResponse<UserResponse>> updateUserStatus(
            @PathVariable Long id,
            @Valid @RequestBody UpdateUserStatusRequest request
    ) {
        return ResponseEntity.ok(userService.updateUserStatus(id, request));
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<BaseResponse<Void>> deleteUser(@PathVariable Long id) {
        return ResponseEntity.ok(userService.deleteUser(id));
    }

    @GetMapping("/count")
    public Long countUsers() {
        return 10L;
    }
}
