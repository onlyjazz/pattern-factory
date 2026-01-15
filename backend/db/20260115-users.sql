--
-- Skeleton user table and auth for multi-tenancy and multi-model access
set search_path to public;
CREATE TABLE users (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    role_id integer NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
-- add role table
CREATE TABLE roles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE
);
-- add user_role table
CREATE TABLE user_role (
    user_id uuid NOT NULL,
    role_id integer NOT NULL,
    PRIMARY KEY (user_id, role_id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (role_id) REFERENCES roles(id)
);
-- add default roles
INSERT INTO roles (name) VALUES ('admin'), ('user');
--
-- add default admin user
INSERT INTO users (email, password_hash, role_id) VALUES ('admin@opencro.com', 'password', 1);
--
-- add active model table
CREATE TABLE active_models (
    user_id uuid NOT NULL,
    model_id integer NOT NULL,
    PRIMARY KEY (user_id, model_id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (model_id) REFERENCES threat.models(id)
);
INSERT INTO active_models (user_id, model_id) VALUES ((SELECT id FROM users WHERE email = 'admin@opencro.com'), 1);
INSERT INTO user_role (user_id, role_id) VALUES ((SELECT id FROM users WHERE email = 'admin@opencro.com'), 1);
--
-- Make basic RBAC infrastructure
--
CREATE TABLE rbac (
    user_id uuid NOT NULL,
    role_id integer NOT NULL,
    permission VARCHAR(255) NOT NULL, -- R, RW, RWD, RWE (Read write tables, execute agents), RWDE (Read write tables, execute agents, delete)
    PRIMARY KEY (user_id, role_id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (role_id) REFERENCES roles(id)
);
INSERT INTO rbac (user_id, role_id, permission) VALUES ((SELECT id FROM users WHERE email = 'admin@opencro.com'), 1, 'RWDE');