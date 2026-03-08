package com.example.dto;

import com.fasterxml.jackson.annotation.JsonInclude;
import jakarta.validation.Valid;
import jakarta.validation.constraints.DecimalMax;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import java.io.Serializable;
import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
@JsonInclude(JsonInclude.Include.NON_NULL)
public class Order implements Serializable {

    private static final long serialVersionUID = 1L;

    @NotNull
    @NotBlank
    @Size(min = 1, max = 50)
    @Pattern(regexp = "^ORD-[0-9]+$")
    private String orderId;

    @NotNull
    @Valid
    private Customer customer;

    @NotNull
    @Size(min = 1)
    private List<OrderItem> items;

    @NotNull
    @Valid
    private OrderStatus status;

    @DecimalMin(value = "0")
    private BigDecimal totalAmount;

    @Size(max = 500)
    private String notes;

    private LocalDateTime createdAt;

    @DecimalMin(value = "1")
    @DecimalMax(value = "5")
    private Long priority;
}
