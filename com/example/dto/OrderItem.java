package com.example.dto;

import com.fasterxml.jackson.annotation.JsonInclude;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import java.io.Serializable;
import java.math.BigDecimal;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
@JsonInclude(JsonInclude.Include.NON_NULL)
public class OrderItem implements Serializable {

    private static final long serialVersionUID = 1L;

    @NotNull
    @NotBlank
    private String productId;

    @Size(max = 200)
    private String productName;

    @NotNull
    @DecimalMin(value = "1")
    private Long quantity;

    @NotNull
    @DecimalMin(value = "0")
    private BigDecimal unitPrice;
}
