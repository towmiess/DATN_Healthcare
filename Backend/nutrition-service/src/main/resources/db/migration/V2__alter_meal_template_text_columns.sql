DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'nutrition_meal_templates'
          AND column_name = 'category'
          AND data_type = 'bytea'
    ) THEN
        ALTER TABLE nutrition_meal_templates
            ALTER COLUMN category TYPE text
            USING convert_from(category, 'UTF8');
    ELSIF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'nutrition_meal_templates'
          AND column_name = 'category'
          AND data_type <> 'text'
    ) THEN
        ALTER TABLE nutrition_meal_templates
            ALTER COLUMN category TYPE text
            USING category::text;
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'nutrition_meal_templates'
          AND column_name = 'cuisine'
          AND data_type = 'bytea'
    ) THEN
        ALTER TABLE nutrition_meal_templates
            ALTER COLUMN cuisine TYPE text
            USING convert_from(cuisine, 'UTF8');
    ELSIF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'nutrition_meal_templates'
          AND column_name = 'cuisine'
          AND data_type <> 'text'
    ) THEN
        ALTER TABLE nutrition_meal_templates
            ALTER COLUMN cuisine TYPE text
            USING cuisine::text;
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'nutrition_meal_templates'
          AND column_name = 'meal_type'
          AND data_type = 'bytea'
    ) THEN
        ALTER TABLE nutrition_meal_templates
            ALTER COLUMN meal_type TYPE text
            USING convert_from(meal_type, 'UTF8');
    ELSIF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'nutrition_meal_templates'
          AND column_name = 'meal_type'
          AND data_type <> 'text'
    ) THEN
        ALTER TABLE nutrition_meal_templates
            ALTER COLUMN meal_type TYPE text
            USING meal_type::text;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_meal_templates_category_lower
    ON nutrition_meal_templates (lower(category));

CREATE INDEX IF NOT EXISTS idx_meal_templates_cuisine_lower
    ON nutrition_meal_templates (lower(cuisine));

CREATE INDEX IF NOT EXISTS idx_meal_templates_meal_type_lower
    ON nutrition_meal_templates (lower(meal_type));
