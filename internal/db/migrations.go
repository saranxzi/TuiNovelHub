package db

import (
	"database/sql"
	"fmt"
)

var migrations = []string{
	`
	CREATE TABLE IF NOT EXISTS novels (
		id              INTEGER PRIMARY KEY AUTOINCREMENT,
		provider_id     TEXT    NOT NULL,
		source_url      TEXT    NOT NULL UNIQUE,
		title           TEXT    NOT NULL,
		author          TEXT,
		cover_url       TEXT,
		description     TEXT,
		status          TEXT    NOT NULL DEFAULT 'Reading',
		priority        INTEGER NOT NULL DEFAULT 2,
		rating          REAL,
		total_chapters  INTEGER NOT NULL DEFAULT 0,
		last_synced_at  DATETIME,
		added_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
	);
	
	CREATE TABLE IF NOT EXISTS chapters (
		id            INTEGER PRIMARY KEY AUTOINCREMENT,
		novel_id      INTEGER NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
		chapter_index INTEGER NOT NULL,
		title         TEXT,
		source_url    TEXT    NOT NULL,
		is_read       BOOLEAN NOT NULL DEFAULT FALSE,
		read_at       DATETIME,
		UNIQUE(novel_id, chapter_index)
	);
	
	CREATE TABLE IF NOT EXISTS reading_history (
		id              INTEGER PRIMARY KEY AUTOINCREMENT,
		novel_id        INTEGER NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
		chapter_id      INTEGER NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
		scroll_offset   INTEGER NOT NULL DEFAULT 0,
		last_read_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
	);
	
	CREATE TABLE IF NOT EXISTS sync_log (
		id         INTEGER PRIMARY KEY AUTOINCREMENT,
		novel_id   INTEGER REFERENCES novels(id) ON DELETE SET NULL,
		event      TEXT NOT NULL,
		detail     TEXT,
		logged_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
	);
	`,

	// Migration 2: add unique index for reading_history upsert
	`CREATE UNIQUE INDEX IF NOT EXISTS idx_reading_history_novel_chapter
	 ON reading_history(novel_id, chapter_id);`,
}

func (db *DB) migrate() error {
	// Create schema_version table if it doesn't exist
	_, err := db.conn.Exec(`
		CREATE TABLE IF NOT EXISTS schema_version (
			version INTEGER PRIMARY KEY
		);
	`)
	if err != nil {
		return err
	}

	var currentVersion int
	err = db.conn.QueryRow(`SELECT COALESCE(MAX(version), 0) FROM schema_version`).Scan(&currentVersion)
	if err != nil && err != sql.ErrNoRows {
		return err
	}

	for i := currentVersion; i < len(migrations); i++ {
		err = db.WithTx(func(tx *sql.Tx) error {
			if _, err := tx.Exec(migrations[i]); err != nil {
				return err
			}
			if _, err := tx.Exec(`INSERT INTO schema_version (version) VALUES (?)`, i+1); err != nil {
				return err
			}
			return nil
		})
		if err != nil {
			return fmt.Errorf("failed to apply migration version %d: %w", i+1, err)
		}
	}

	return nil
}
