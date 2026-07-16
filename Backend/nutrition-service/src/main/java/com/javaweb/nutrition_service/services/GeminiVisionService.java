package com.javaweb.nutrition_service.services;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.javaweb.nutrition_service.config.GeminiVisionProperties;
import com.javaweb.nutrition_service.dto.TokenPayload;
import com.javaweb.nutrition_service.dto.request.VisionAnalyzeRequest;
import com.javaweb.nutrition_service.dto.response.VisionAnalyzeResponse;
import com.javaweb.nutrition_service.dto.response.VisionFoodItemResponse;
import com.javaweb.nutrition_service.dto.response.VisionIngredientMatchResponse;
import com.javaweb.nutrition_service.entity.IngredientEntity;
import com.javaweb.nutrition_service.entity.MealHistoryEntity;
import com.javaweb.nutrition_service.repository.IngredientRepository;
import com.javaweb.nutrition_service.repository.MealHistoryRepository;
import com.javaweb.nutrition_service.util.CurrentTokenPayloadUtil;
import com.javaweb.nutrition_service.util.IngredientSearchUtil;
import com.javaweb.nutrition_service.util.MealHistoryMapperUtil;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;
import org.springframework.web.client.HttpStatusCodeException;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.web.util.UriComponentsBuilder;

import java.io.IOException;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.net.URI;
import java.util.ArrayList;
import java.util.Base64;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

@Slf4j
@Service
@RequiredArgsConstructor
public class GeminiVisionService {

    private static final int MAX_CANDIDATES = 30;
    private static final int MAX_OUTPUT_TOKENS = 4096;
    private static final BigDecimal HUNDRED = BigDecimal.valueOf(100);
    private static final String COMBINED_PROMPT = """
            Phan tich anh mon an va tra ve CHI JSON hop le theo schema.
            Yeu cau:
            - Tra ve 2 truong: name va foods.
            - name la ten mon an chuan bang tieng Viet, viet thuong, ngan gon.
            - foods la danh sach nguyen lieu thuc su nhin thay trong anh.
            - foodName la ten nguyen lieu bang tieng Viet.
            - weightGram la so nguyen.
            - caloriesPer100Gram, proteinPer100Gram, fatPer100Gram, carbsPer100Gram la dinh duong uoc tinh
              tren 100 gram cua chinh nguyen lieu do.
            - Neu khong co the suy luan chinh xac, hay uoc tinh theo nguyen lieu pho bien gan nhat.
            - Khong them nguyen lieu khong nhin thay. Neu khong chac thi bo qua.
            - Khong them nguyen lieu khong nhin thay. Neu khong chac thi bo qua.
            - Neu mon la chao, com rang, pho, bun, mi, sup hoac mon ham/vua co phan nen chinh ro rang, hay them nguyen lieu nen chinh do neu co the suy luan vung chac.
            - Khong markdown, khong code fence, khong giai thich.
            """;

    private final GeminiVisionProperties geminiVisionProperties;
    private final RestTemplate geminiRestTemplate;
    private final ObjectMapper objectMapper;
    private final CurrentTokenPayloadUtil currentTokenPayloadUtil;
    private final IngredientRepository ingredientRepository;
    private final IngredientSearchUtil ingredientSearchUtil;
    private final MealHistoryRepository mealHistoryRepository;
    private final MealHistoryMapperUtil mealHistoryMapperUtil;

    public VisionAnalyzeResponse analyze(VisionAnalyzeRequest request) {
        String imageUrl = validateAndNormalizeImageUrl(request.getUrl());
        DownloadedImage downloadedImage = resolveImageForRecognition(request.getImage(), imageUrl);

        String modelJson = callGemini(buildPayload(
                downloadedImage.bytes(),
                downloadedImage.mimeType(),
                COMBINED_PROMPT,
                buildCombinedSchema(),
                MAX_OUTPUT_TOKENS
        ));

        JsonNode root = parseJsonNodeSafely(modelJson);
        String mealName = parseName(root);
        List<VisionFoodItemResponse> foods = parseFoods(root);

        MealNutritionAnalysis nutritionAnalysis = calculateNutrition(foods);
        TokenPayload tokenPayload = currentTokenPayloadUtil.getCurrentTokenPayload();
        MealHistoryEntity saved = mealHistoryRepository.save(
                mealHistoryMapperUtil.toEntity(
                        tokenPayload.getUserId(),
                        imageUrl,
                        mealName,
                        nutritionAnalysis.totalCalories(),
                        nutritionAnalysis.totalProtein(),
                        nutritionAnalysis.totalFat(),
                        nutritionAnalysis.totalCarbs()
                )
        );

        VisionAnalyzeResponse response = mealHistoryMapperUtil.toResponse(saved);
        response.setDetectedFoods(List.copyOf(foods));
        response.setIngredientMatches(List.copyOf(nutritionAnalysis.ingredientMatches()));
        return response;
    }

    private String validateAndNormalizeImageUrl(String imageUrl) {
        if (!StringUtils.hasText(imageUrl)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "url is required");
        }

        return imageUrl.trim();
    }

    private DownloadedImage resolveImageForRecognition(MultipartFile image, String imageUrl) {
        if (image != null && !image.isEmpty()) {
            return readUploadedImage(image);
        }

        return downloadImage(imageUrl);
    }

    private DownloadedImage readUploadedImage(MultipartFile image) {
        try {
            byte[] bytes = image.getBytes();
            if (bytes.length == 0) {
                throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Uploaded image is empty");
            }

            String mimeType = StringUtils.hasText(image.getContentType())
                    ? image.getContentType()
                    : guessMimeType(image.getOriginalFilename());

            return new DownloadedImage(bytes, mimeType);
        } catch (IOException ex) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Unable to read uploaded image", ex);
        }
    }

    private DownloadedImage downloadImage(String imageUrl) {
        try {
            URI uri = URI.create(imageUrl);
            ResponseEntity<byte[]> response = geminiRestTemplate.exchange(uri, HttpMethod.GET, HttpEntity.EMPTY, byte[].class);

            if (!response.getStatusCode().is2xxSuccessful() || response.getBody() == null || response.getBody().length == 0) {
                throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Unable to download image from url");
            }

            MediaType contentType = response.getHeaders().getContentType();
            String mimeType = contentType != null ? contentType.toString() : guessMimeType(imageUrl);

            return new DownloadedImage(response.getBody(), mimeType);
        } catch (IllegalArgumentException ex) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Invalid image url", ex);
        } catch (RestClientException ex) {
            throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "Unable to fetch image from url", ex);
        }
    }

    private String guessMimeType(String value) {
        if (!StringUtils.hasText(value)) {
            return MediaType.IMAGE_JPEG_VALUE;
        }

        String lower = value.toLowerCase(Locale.ROOT);
        if (lower.endsWith(".png")) {
            return MediaType.IMAGE_PNG_VALUE;
        }
        if (lower.endsWith(".webp")) {
            return "image/webp";
        }
        if (lower.endsWith(".gif")) {
            return MediaType.IMAGE_GIF_VALUE;
        }
        if (lower.endsWith(".bmp")) {
            return "image/bmp";
        }
        if (lower.endsWith(".tif") || lower.endsWith(".tiff")) {
            return "image/tiff";
        }
        return MediaType.IMAGE_JPEG_VALUE;
    }

    private Map<String, Object> buildPayload(
            byte[] imageBytes,
            String mimeType,
            String prompt,
            Map<String, Object> responseSchema,
            int maxOutputTokens
    ) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("systemInstruction", buildSystemInstruction(prompt));
        payload.put("contents", List.of(buildUserContent(imageBytes, mimeType)));
        payload.put("generationConfig", buildGenerationConfig(responseSchema, maxOutputTokens));
        return payload;
    }

    private Map<String, Object> buildSystemInstruction(String prompt) {
        Map<String, Object> instruction = new LinkedHashMap<>();
        instruction.put("parts", List.of(Map.of("text", prompt)));
        return instruction;
    }

    private Map<String, Object> buildUserContent(byte[] imageBytes, String mimeType) {
        Map<String, Object> content = new LinkedHashMap<>();
        content.put("role", "user");
        content.put("parts", List.of(buildImagePart(imageBytes, mimeType)));
        return content;
    }

    private Map<String, Object> buildImagePart(byte[] imageBytes, String mimeType) {
        Map<String, Object> inlineData = new LinkedHashMap<>();
        inlineData.put("mime_type", mimeType);
        inlineData.put("data", Base64.getEncoder().encodeToString(imageBytes));

        Map<String, Object> part = new LinkedHashMap<>();
        part.put("inline_data", inlineData);
        return part;
    }

    private Map<String, Object> buildGenerationConfig(Map<String, Object> responseSchema, int maxOutputTokens) {
        Map<String, Object> generationConfig = new LinkedHashMap<>();
        generationConfig.put("temperature", 0.0d);
        generationConfig.put("maxOutputTokens", maxOutputTokens);
        generationConfig.put("responseMimeType", "application/json");
        generationConfig.put("responseSchema", responseSchema);
        return generationConfig;
    }

    private Map<String, Object> buildCombinedSchema() {
        Map<String, Object> foodItemSchema = new LinkedHashMap<>();
        foodItemSchema.put("type", "object");
        foodItemSchema.put("required", List.of(
                "foodName",
                "weightGram",
                "caloriesPer100Gram",
                "proteinPer100Gram",
                "fatPer100Gram",
                "carbsPer100Gram"
        ));
        foodItemSchema.put("properties", Map.of(
                "foodName", Map.of(
                        "type", "string",
                        "description", "Ten nguyen lieu bang tieng Viet"
                ),
                "weightGram", Map.of(
                        "type", "integer",
                        "description", "Khoi luong uoc luong theo gram"
                ),
                "caloriesPer100Gram", Map.of(
                        "type", "number",
                        "description", "Calories uoc tinh tren 100 gram"
                ),
                "proteinPer100Gram", Map.of(
                        "type", "number",
                        "description", "Protein uoc tinh tren 100 gram"
                ),
                "fatPer100Gram", Map.of(
                        "type", "number",
                        "description", "Fat uoc tinh tren 100 gram"
                ),
                "carbsPer100Gram", Map.of(
                        "type", "number",
                        "description", "Carbs uoc tinh tren 100 gram"
                )
        ));

        Map<String, Object> schema = new LinkedHashMap<>();
        schema.put("type", "object");
        schema.put("required", List.of("name", "foods"));
        schema.put("properties", Map.of(
                "name", Map.of(
                        "type", "string",
                        "description", "Ten chuan cua mon an bang tieng Viet"
                ),
                "foods", Map.of(
                        "type", "array",
                        "items", foodItemSchema
                )
        ));
        return schema;
    }

    private String callGemini(Map<String, Object> payload) {
        String apiKey = geminiVisionProperties.getApiKey();
        if (!StringUtils.hasText(apiKey) || "change-me-in-production".equalsIgnoreCase(apiKey.trim())) {
            throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR, "Gemini API key is not configured");
        }

        String url = UriComponentsBuilder
                .fromHttpUrl(geminiVisionProperties.getBaseUrl())
                .path("/models/{model}:generateContent")
                .buildAndExpand(geminiVisionProperties.getModel())
                .toUriString();

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.setAccept(List.of(MediaType.APPLICATION_JSON));
        headers.set("x-goog-api-key", apiKey);

        try {
            ResponseEntity<String> response = geminiRestTemplate.postForEntity(
                    url,
                    new HttpEntity<>(payload, headers),
                    String.class
            );
            if (!response.getStatusCode().is2xxSuccessful() || !StringUtils.hasText(response.getBody())) {
                throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "Gemini Vision returned an empty response");
            }
            return extractModelJson(response.getBody());
        } catch (HttpStatusCodeException ex) {
            log.error("Gemini Vision request failed with status {} and body {}",
                    ex.getStatusCode(), ex.getResponseBodyAsString());
            throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "Failed to analyze image with Gemini Vision", ex);
        } catch (RestClientException ex) {
            log.error("Gemini Vision request failed", ex);
            throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "Failed to analyze image with Gemini Vision", ex);
        }
    }

    private String extractModelJson(String responseBody) {
        try {
            JsonNode root = objectMapper.readTree(responseBody);
            JsonNode candidates = root.path("candidates");
            if (!candidates.isArray() || candidates.isEmpty()) {
                throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "Gemini Vision response does not contain candidates");
            }

            JsonNode parts = candidates.get(0).path("content").path("parts");
            if (!parts.isArray() || parts.isEmpty()) {
                throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "Gemini Vision response does not contain content parts");
            }

            StringBuilder textBuilder = new StringBuilder();
            for (JsonNode part : parts) {
                String partText = part.path("text").asText("");
                if (StringUtils.hasText(partText)) {
                    textBuilder.append(partText.trim());
                }
            }

            String text = textBuilder.toString().trim();
            if (!StringUtils.hasText(text)) {
                throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "Gemini Vision response does not contain JSON text");
            }
            return text;
        } catch (JsonProcessingException ex) {
            throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "Unable to parse Gemini Vision response", ex);
        }
    }

    private JsonNode parseJsonNodeSafely(String modelJson) {
        try {
            return objectMapper.readTree(modelJson);
        } catch (JsonProcessingException firstError) {
            int start = modelJson.indexOf('{');
            int end = modelJson.lastIndexOf('}');
            if (start >= 0 && end > start) {
                try {
                    return objectMapper.readTree(modelJson.substring(start, end + 1));
                } catch (JsonProcessingException ignored) {
                    // Fall through to original error below.
                }
            }
            throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "Gemini Vision returned invalid JSON", firstError);
        }
    }

    private String parseName(JsonNode root) {
        String name = root.path("name").asText("").trim();
        if (!StringUtils.hasText(name)) {
            throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "Gemini Vision response does not contain dish name");
        }
        return normalizeDishName(name);
    }

    private List<VisionFoodItemResponse> parseFoods(JsonNode root) {
        JsonNode foodsNode = root.path("foods");
        if (!foodsNode.isArray()) {
            throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "Gemini Vision JSON does not contain foods array");
        }

        List<VisionFoodItemResponse> foods = new ArrayList<>();
        for (JsonNode foodNode : foodsNode) {
            String foodName = foodNode.path("foodName").asText("").trim();
            int weightGram = foodNode.path("weightGram").asInt(0);
            BigDecimal caloriesPer100Gram = readBigDecimal(foodNode, "caloriesPer100Gram");
            BigDecimal proteinPer100Gram = readBigDecimal(foodNode, "proteinPer100Gram");
            BigDecimal fatPer100Gram = readBigDecimal(foodNode, "fatPer100Gram");
            BigDecimal carbsPer100Gram = readBigDecimal(foodNode, "carbsPer100Gram");

            if (!StringUtils.hasText(foodName) || weightGram <= 0) {
                continue;
            }

            foods.add(VisionFoodItemResponse.builder()
                    .foodName(normalizeFoodName(foodName))
                    .weightGram(weightGram)
                    .caloriesPer100Gram(caloriesPer100Gram)
                    .proteinPer100Gram(proteinPer100Gram)
                    .fatPer100Gram(fatPer100Gram)
                    .carbsPer100Gram(carbsPer100Gram)
                    .build());
        }

        return foods;
    }

    private MealNutritionAnalysis calculateNutrition(List<VisionFoodItemResponse> foods) {
        BigDecimal totalCalories = BigDecimal.ZERO;
        BigDecimal totalProtein = BigDecimal.ZERO;
        BigDecimal totalFat = BigDecimal.ZERO;
        BigDecimal totalCarbs = BigDecimal.ZERO;
        List<VisionIngredientMatchResponse> ingredientMatches = new ArrayList<>();

        for (VisionFoodItemResponse food : foods) {
            RankedIngredient matchedIngredient = resolveBestIngredient(food.getFoodName());
            BigDecimal weightFactor = BigDecimal.valueOf(food.getWeightGram())
                    .divide(HUNDRED, 6, RoundingMode.HALF_UP);
            if (matchedIngredient == null) {
                totalCalories = totalCalories.add(calculateNutrient(food.getCaloriesPer100Gram(), weightFactor));
                totalProtein = totalProtein.add(calculateNutrient(food.getProteinPer100Gram(), weightFactor));
                totalFat = totalFat.add(calculateNutrient(food.getFatPer100Gram(), weightFactor));
                totalCarbs = totalCarbs.add(calculateNutrient(food.getCarbsPer100Gram(), weightFactor));
                ingredientMatches.add(buildUnmatchedIngredientDebug(food));
                continue;
            }

            IngredientEntity ingredient = matchedIngredient.ingredient();
            BigDecimal caloriesPer100Gram = resolveNutrientValue(ingredient.getCalories(), food.getCaloriesPer100Gram());
            BigDecimal proteinPer100Gram = resolveNutrientValue(ingredient.getProtein(), food.getProteinPer100Gram());
            BigDecimal fatPer100Gram = resolveNutrientValue(ingredient.getFat(), food.getFatPer100Gram());
            BigDecimal carbsPer100Gram = resolveNutrientValue(ingredient.getCarbs(), food.getCarbsPer100Gram());

            totalCalories = totalCalories.add(calculateNutrient(caloriesPer100Gram, weightFactor));
            totalProtein = totalProtein.add(calculateNutrient(proteinPer100Gram, weightFactor));
            totalFat = totalFat.add(calculateNutrient(fatPer100Gram, weightFactor));
            totalCarbs = totalCarbs.add(calculateNutrient(carbsPer100Gram, weightFactor));
            ingredientMatches.add(buildMatchedIngredientDebug(
                    food,
                    matchedIngredient,
                    caloriesPer100Gram,
                    proteinPer100Gram,
                    fatPer100Gram,
                    carbsPer100Gram
            ));
        }

        return new MealNutritionAnalysis(
                scale(totalCalories),
                scale(totalProtein),
                scale(totalFat),
                scale(totalCarbs),
                ingredientMatches
        );
    }

    private RankedIngredient resolveBestIngredient(String foodName) {
        IngredientSearchUtil.SearchTerms searchTerms = ingredientSearchUtil.buildSearchTerms(foodName);
        List<IngredientEntity> candidates = ingredientRepository.searchCandidates(
                searchTerms.exactFoodName(),
                searchTerms.exactNormalizedName(),
                searchTerms.foodNamePrefix(),
                searchTerms.normalizedNamePrefix(),
                searchTerms.foodNameContains(),
                searchTerms.normalizedNameContains(),
                MAX_CANDIDATES
        );

        return candidates.stream()
                .map(candidate -> new RankedIngredient(candidate, rankCandidate(searchTerms, candidate)))
                .sorted(Comparator
                        .comparingInt(RankedIngredient::tier)
                        .thenComparing(Comparator.comparingDouble(RankedIngredient::similarity).reversed())
                        .thenComparingLong(candidate -> candidate.ingredient().getId() == null ? Long.MAX_VALUE : candidate.ingredient().getId()))
                .findFirst()
                .orElse(null);
    }

    private CandidateRank rankCandidate(IngredientSearchUtil.SearchTerms searchTerms, IngredientEntity candidate) {
        String candidateFoodName = ingredientSearchUtil.normalizeDisplayLower(candidate.getFoodName());
        String candidateNormalizedName = ingredientSearchUtil.normalizeComparisonKey(
                StringUtils.hasText(candidate.getNormalizedName()) ? candidate.getNormalizedName() : candidate.getFoodName()
        );

        int tier;
        if (candidateFoodName.equals(searchTerms.exactFoodName())) {
            tier = 0;
        } else if (candidateNormalizedName.equals(searchTerms.exactNormalizedName())) {
            tier = 1;
        } else if (candidateFoodName.startsWith(searchTerms.exactFoodName())) {
            tier = 2;
        } else if (candidateNormalizedName.startsWith(searchTerms.exactNormalizedName())) {
            tier = 3;
        } else if (candidateFoodName.contains(searchTerms.exactFoodName())) {
            tier = 4;
        } else if (candidateNormalizedName.contains(searchTerms.exactNormalizedName())) {
            tier = 5;
        } else {
            tier = 6;
        }

        double similarity = Math.max(
                ingredientSearchUtil.levenshteinSimilarity(searchTerms.exactNormalizedName(), candidateNormalizedName),
                ingredientSearchUtil.levenshteinSimilarity(searchTerms.exactFoodName(), candidateFoodName)
        );

        return new CandidateRank(tier, similarity);
    }

    private BigDecimal calculateNutrient(BigDecimal nutrientPer100Gram, BigDecimal weightFactor) {
        BigDecimal source = nutrientPer100Gram == null ? BigDecimal.ZERO : nutrientPer100Gram;
        return source.multiply(weightFactor);
    }

    private BigDecimal resolveNutrientValue(BigDecimal preferred, BigDecimal fallback) {
        if (preferred != null && preferred.compareTo(BigDecimal.ZERO) > 0) {
            return preferred;
        }
        if (fallback != null && fallback.compareTo(BigDecimal.ZERO) > 0) {
            return fallback;
        }
        return BigDecimal.ZERO;
    }

    private VisionIngredientMatchResponse buildMatchedIngredientDebug(
            VisionFoodItemResponse food,
            RankedIngredient matchedIngredient,
            BigDecimal caloriesPer100Gram,
            BigDecimal proteinPer100Gram,
            BigDecimal fatPer100Gram,
            BigDecimal carbsPer100Gram
    ) {
        IngredientEntity ingredient = matchedIngredient.ingredient();
        return VisionIngredientMatchResponse.builder()
                .sourceFoodName(food.getFoodName())
                .inputWeightGram(food.getWeightGram())
                .matched(Boolean.TRUE)
                .matchedIngredientId(ingredient.getId())
                .matchedFoodName(ingredient.getFoodName())
                .matchedNormalizedName(ingredient.getNormalizedName())
                .caloriesPer100Gram(caloriesPer100Gram)
                .proteinPer100Gram(proteinPer100Gram)
                .fatPer100Gram(fatPer100Gram)
                .carbsPer100Gram(carbsPer100Gram)
                .similarity(matchedIngredient.similarity())
                .build();
    }

    private VisionIngredientMatchResponse buildUnmatchedIngredientDebug(VisionFoodItemResponse food) {
        return VisionIngredientMatchResponse.builder()
                .sourceFoodName(food.getFoodName())
                .inputWeightGram(food.getWeightGram())
                .matched(Boolean.FALSE)
                .caloriesPer100Gram(food.getCaloriesPer100Gram())
                .proteinPer100Gram(food.getProteinPer100Gram())
                .fatPer100Gram(food.getFatPer100Gram())
                .carbsPer100Gram(food.getCarbsPer100Gram())
                .similarity(0.0d)
                .build();
    }

    private BigDecimal readBigDecimal(JsonNode node, String fieldName) {
        JsonNode field = node.path(fieldName);
        if (field.isMissingNode() || field.isNull()) {
            return BigDecimal.ZERO;
        }

        if (field.isNumber()) {
            return field.decimalValue();
        }

        String text = field.asText("").trim();
        if (!StringUtils.hasText(text)) {
            return BigDecimal.ZERO;
        }

        try {
            return new BigDecimal(text);
        } catch (NumberFormatException ex) {
            return BigDecimal.ZERO;
        }
    }

    private BigDecimal scale(BigDecimal value) {
        return (value == null ? BigDecimal.ZERO : value).setScale(2, RoundingMode.HALF_UP);
    }

    private String normalizeDishName(String value) {
        String normalized = value.trim().replaceAll("\\s+", " ");
        return normalized.toLowerCase(Locale.ROOT);
    }

    private String normalizeFoodName(String value) {
        String normalized = value.trim().replaceAll("\\s+", " ");
        if (normalized.isEmpty()) {
            return normalized;
        }
        return normalized.substring(0, 1).toUpperCase(Locale.ROOT) + normalized.substring(1);
    }

    private record DownloadedImage(byte[] bytes, String mimeType) {
    }

    private record MealNutritionAnalysis(
            BigDecimal totalCalories,
            BigDecimal totalProtein,
            BigDecimal totalFat,
            BigDecimal totalCarbs,
            List<VisionIngredientMatchResponse> ingredientMatches
    ) {
    }

    private record CandidateRank(int tier, double similarity) {
    }

    private record RankedIngredient(IngredientEntity ingredient, CandidateRank rank) {
        private int tier() {
            return rank.tier();
        }

        private double similarity() {
            return rank.similarity();
        }
    }
}
