CREATE TABLE IF NOT EXISTS roles (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    full_name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    phone_number VARCHAR(50) NOT NULL,
    password VARCHAR(255) NOT NULL,
    change_pass_at TIMESTAMPTZ NULL,
    status VARCHAR(50) NOT NULL,
    avatar VARCHAR(255) NULL,
    deleted BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS users_roles (
    user_id BIGINT NOT NULL,
    role_id BIGINT NOT NULL,
    PRIMARY KEY (user_id, role_id),
    CONSTRAINT fk_users_roles_user
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_users_roles_role
        FOREIGN KEY (role_id) REFERENCES roles (id) ON DELETE CASCADE
);

INSERT INTO roles (id, name)
VALUES
    (1, 'ADMIN'),
    (2, 'USER')
ON CONFLICT (id) DO UPDATE
SET name = EXCLUDED.name;

SELECT setval(
    pg_get_serial_sequence('roles', 'id'),
    COALESCE((SELECT MAX(id) FROM roles), 1),
    true
);

INSERT INTO users (
    id,
    full_name,
    email,
    phone_number,
    password,
    change_pass_at,
    status,
    avatar,
    deleted
)
VALUES (
    1,
    U&'L\00EA \0110\00ECnh T\00FA',
    'letu260203@gmail.com',
    '0377928141',
    'admin',
    NULL,
    'ACTIVE',
    NULL,
    FALSE
)
ON CONFLICT (id) DO UPDATE
SET
    full_name = EXCLUDED.full_name,
    email = EXCLUDED.email,
    phone_number = EXCLUDED.phone_number,
    password = EXCLUDED.password,
    change_pass_at = EXCLUDED.change_pass_at,
    status = EXCLUDED.status,
    avatar = EXCLUDED.avatar,
    deleted = EXCLUDED.deleted;

INSERT INTO users_roles (user_id, role_id)
VALUES (1, 1)
ON CONFLICT (user_id, role_id) DO NOTHING;

SELECT setval(
    pg_get_serial_sequence('users', 'id'),
    COALESCE((SELECT MAX(id) FROM users), 1),
    true
);
