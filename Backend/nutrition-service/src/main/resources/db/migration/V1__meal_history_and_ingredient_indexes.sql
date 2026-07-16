create table if not exists meal_history (
    id bigserial primary key,
    user_id bigint not null,
    image varchar(512),
    name varchar(255),
    total_calories numeric(12,2),
    total_protein numeric(12,2),
    total_fat numeric(12,2),
    total_carbs numeric(12,2),
    created_at timestamp not null default now(),
    updated_at timestamp not null default now()
);

create index if not exists idx_meal_history_user_created_at
    on meal_history (user_id, created_at desc);

create index if not exists idx_ingredient_food_name_lower
    on ingredient (lower(food_name));

create index if not exists idx_ingredient_normalized_name_lower
    on ingredient (lower(normalized_name));
