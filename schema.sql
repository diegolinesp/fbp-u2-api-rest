-- Crea la base de datos y las tablas de la API.

CREATE DATABASE IF NOT EXISTS spotify_api
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE spotify_api;

-- Usuarios de la API
CREATE TABLE IF NOT EXISTS users (
    id          INT             AUTO_INCREMENT PRIMARY KEY,
    username    VARCHAR(50)     NOT NULL UNIQUE,
    email       VARCHAR(255)    NOT NULL UNIQUE,
    full_name   VARCHAR(100),
    created_at  TIMESTAMP       DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP       DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Preferencias musicales: géneros favoritos de cada usuario
CREATE TABLE IF NOT EXISTS user_genres (
    user_id     INT             NOT NULL,
    genre       VARCHAR(50)     NOT NULL,
    PRIMARY KEY (user_id, genre),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Caché local de artistas de Spotify
CREATE TABLE IF NOT EXISTS artists (
    id          VARCHAR(22)     PRIMARY KEY,        -- ID de Spotify
    name        VARCHAR(255)    NOT NULL,
    spotify_url VARCHAR(255),
    image_url   VARCHAR(500),
    cached_at   TIMESTAMP       DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Caché local de canciones de Spotify
CREATE TABLE IF NOT EXISTS tracks (
    id           VARCHAR(22)     PRIMARY KEY,           -- ID de Spotify
    name         VARCHAR(255)    NOT NULL,
    artist_names VARCHAR(255)    NOT NULL,              -- artistas separados por comas
    album_name   VARCHAR(255),
    duration_ms  INT             NOT NULL,
    spotify_url  VARCHAR(255),
    cached_at    TIMESTAMP       DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Artistas favoritos de cada usuario
CREATE TABLE IF NOT EXISTS user_favorite_artists (
    user_id     INT             NOT NULL,
    artist_id   VARCHAR(22)     NOT NULL,
    added_at    TIMESTAMP       DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, artist_id),
    FOREIGN KEY (user_id)   REFERENCES users(id)    ON DELETE CASCADE,
    FOREIGN KEY (artist_id) REFERENCES artists(id)
);

-- Canciones favoritas de cada usuario
CREATE TABLE IF NOT EXISTS user_favorite_tracks (
    user_id     INT             NOT NULL,
    track_id    VARCHAR(22)     NOT NULL,
    added_at    TIMESTAMP       DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, track_id),
    FOREIGN KEY (user_id)   REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (track_id)  REFERENCES tracks(id)
);
