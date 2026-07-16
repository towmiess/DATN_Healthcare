package com.javaweb.nutrition_service.controller;

import com.javaweb.nutrition_service.dto.request.VisionAnalyzeRequest;
import com.javaweb.nutrition_service.dto.response.VisionAnalyzeResponse;
import com.javaweb.nutrition_service.services.GeminiVisionService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ModelAttribute;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequiredArgsConstructor
@RequestMapping("/api/vision")
public class GeminiVisionController {

    private final GeminiVisionService geminiVisionService;

    @PostMapping(value = "/analyze", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<VisionAnalyzeResponse> analyze(@Valid @ModelAttribute VisionAnalyzeRequest request) {
        return ResponseEntity.ok(geminiVisionService.analyze(request));
    }

    @PostMapping(value = "/analyze", consumes = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<VisionAnalyzeResponse> analyzeJson(@Valid @RequestBody VisionAnalyzeRequest request) {
        return ResponseEntity.ok(geminiVisionService.analyze(request));
    }
}
