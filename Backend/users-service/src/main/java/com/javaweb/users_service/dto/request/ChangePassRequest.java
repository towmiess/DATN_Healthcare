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
public class ChangePassRequest {

    @NotBlank(message = "OldPassWord is require!")
    private String oldPassword;
    @NotBlank(message = "NewPassword is require!")
    private String newPassword;
    @NotBlank(message = "NewPasswordConfirm is require!")
    private String newPasswordConfirm;
}
