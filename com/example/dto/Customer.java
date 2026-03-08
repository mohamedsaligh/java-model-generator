package com.example.dto;

import com.fasterxml.jackson.annotation.JsonInclude;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import java.io.Serializable;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
@JsonInclude(JsonInclude.Include.NON_NULL)
public class Customer implements Serializable {

    private static final long serialVersionUID = 1L;

    @NotNull
    @NotBlank
    @Size(min = 1, max = 100)
    private String name;

    @NotNull
    @NotBlank
    @Email
    private String email;

    @Pattern(regexp = "^\\+?[0-9\\-\\s]+$")
    private String phone;

    @Valid
    private Address address;
}
