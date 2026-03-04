package com.javaweb.users_service.controller;

import com.javaweb.users_service.dto.response.BaseResponse;
import com.javaweb.users_service.dto.response.UserResponse;
import com.javaweb.users_service.services.Impl.UserService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequiredArgsConstructor
@RequestMapping("/api/users")
public class UserController {
    private final UserService userService;

    @GetMapping
    public ResponseEntity<BaseResponse<List<UserResponse>>> getAllUsers(@RequestParam Map<String, Object> params) {
        return ResponseEntity.ok().body(userService.getAllUsers(params));
    }
}
