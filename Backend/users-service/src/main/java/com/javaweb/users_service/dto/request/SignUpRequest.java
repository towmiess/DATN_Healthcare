package com.javaweb.users_service.dto.request;

import jakarta.validation.constraints.NotBlank;
import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
public class SignUpRequest {
    @NotBlank(message = "FullName is required!")
    private String fullName;

    @NotBlank(message = "Email is required!")
    private String email;

    @NotBlank(message = "PhoneNumber is required!")
    private String phoneNumber;

    @NotBlank(message = "Username is required")
    private String username;

    @NotBlank(message = "Password is required!")
    private String password;

    @NotBlank(message = "ConfirmPassword is required!")
    private String confirmPassword;
}
