package com.example.dto;

import com.fasterxml.jackson.annotation.JsonInclude;
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
public class Address implements Serializable {

    private static final long serialVersionUID = 1L;

    @NotNull
    @NotBlank
    @Size(max = 200)
    private String street;

    @NotNull
    @NotBlank
    @Size(max = 100)
    private String city;

    @Size(max = 100)
    private String state;

    @Pattern(regexp = "^[0-9]{5}(-[0-9]{4})?$")
    private String zipCode;

    @NotNull
    @NotBlank
    @Size(min = 2, max = 2)
    private String country;
}
