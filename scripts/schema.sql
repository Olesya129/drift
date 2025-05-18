-- Удаление существующих таблиц
DROP TABLE IF EXISTS Cars CASCADE;
DROP TABLE IF EXISTS Payments CASCADE;
DROP TABLE IF EXISTS Reviews CASCADE;
DROP TABLE IF EXISTS Registrations CASCADE;
DROP TABLE IF EXISTS Events CASCADE;
DROP TABLE IF EXISTS Locations CASCADE;
DROP TABLE IF EXISTS Users CASCADE;

-- Удаление существующих типов
DROP TYPE IF EXISTS user_role CASCADE;
DROP TYPE IF EXISTS event_status CASCADE;
DROP TYPE IF EXISTS registration_status CASCADE;
DROP TYPE IF EXISTS payment_status CASCADE;
DROP TYPE IF EXISTS registration_role CASCADE;

-- Создание пользовательских типов ENUM 
CREATE TYPE user_role AS ENUM ('участник', 'организатор');
CREATE TYPE event_status AS ENUM ('запланировано', 'завершено', 'отменено');
CREATE TYPE registration_status AS ENUM ('зарегистрировано', 'отменено');
CREATE TYPE payment_status AS ENUM ('ожидает оплаты', 'оплачено');
CREATE TYPE registration_role AS ENUM ('зритель', 'участник');

-- Создание таблиц
CREATE TABLE Users (
    user_id SERIAL PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(100) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    role user_role DEFAULT 'участник',
    city VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT valid_email CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')
);

CREATE TABLE Locations (
    location_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    address VARCHAR(255) NOT NULL,
    city VARCHAR(50) NOT NULL,
    capacity INTEGER NOT NULL CHECK (capacity > 0)
);

CREATE TABLE Events (
    event_id SERIAL PRIMARY KEY,
    title VARCHAR(100) NOT NULL,
    description TEXT,
    date TIMESTAMP NOT NULL,
    location_id INTEGER REFERENCES Locations(location_id) ON DELETE RESTRICT,
    organizer_id INTEGER REFERENCES Users(user_id) ON DELETE CASCADE,
    spectator_price DECIMAL(10, 2) DEFAULT 500.00,
    participant_price DECIMAL(10, 2) DEFAULT 2000.00,
    status event_status DEFAULT 'запланировано',
    photo_url VARCHAR(255)
);

CREATE TABLE Registrations (
    registration_id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES Users(user_id) ON DELETE CASCADE,
    event_id INTEGER REFERENCES Events(event_id) ON DELETE CASCADE,
    registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status registration_status DEFAULT 'зарегистрировано',
    role registration_role NOT NULL
);

CREATE TABLE Reviews (
    review_id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES Users(user_id) ON DELETE CASCADE,
    event_id INTEGER REFERENCES Events(event_id) ON DELETE CASCADE,
    rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE Payments (
    payment_id SERIAL PRIMARY KEY,
    registration_id INTEGER REFERENCES Registrations(registration_id) ON DELETE CASCADE,
    amount DECIMAL(10, 2) NOT NULL,
    payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status payment_status DEFAULT 'ожидает оплаты'
);

CREATE TABLE Cars (
    car_id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES Users(user_id) ON DELETE CASCADE,
    event_id INTEGER REFERENCES Events(event_id) ON DELETE SET NULL,
    model VARCHAR(100) NOT NULL,
    year INTEGER CHECK (year > 1900 AND year <= 2025),
    color VARCHAR(50),
    photo_url VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_events_date ON Events(date);
