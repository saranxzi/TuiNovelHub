package db

import (
	"database/sql"
	"fmt"
	"time"

	"treading/internal/providers"
)

// AddNovel inserts a novel into the database or updates it if it exists.
func (db *DB) AddNovel(novel *Novel) error {
	query := `
		INSERT INTO novels (provider_id, source_url, title, author, cover_url, description, status, total_chapters)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?)
		ON CONFLICT(source_url) DO UPDATE SET
			title = excluded.title,
			cover_url = excluded.cover_url,
			description = excluded.description,
			status = excluded.status,
			total_chapters = excluded.total_chapters
		RETURNING id, added_at, priority, rating
	`

	var author, coverURL, description sql.NullString
	if novel.Author != "" {
		author = sql.NullString{String: novel.Author, Valid: true}
	}
	if novel.CoverURL != "" {
		coverURL = sql.NullString{String: novel.CoverURL, Valid: true}
	}
	if novel.Description != "" {
		description = sql.NullString{String: novel.Description, Valid: true}
	}

	var rating sql.NullFloat64

	err := db.conn.QueryRow(
		query,
		novel.ProviderID, novel.SourceURL, novel.Title, author, coverURL, description, novel.Status, novel.TotalChapters,
	).Scan(&novel.ID, &novel.AddedAt, &novel.Priority, &rating)

	if err != nil {
		return fmt.Errorf("failed to insert novel: %w", err)
	}

	if rating.Valid {
		novel.Rating = rating.Float64
	}
	return nil
}

// scanner is an interface satisfied by both *sql.Row and *sql.Rows.
type scanner interface {
	Scan(dest ...interface{}) error
}

func scanNovelRow(s scanner) (Novel, error) {
	var n Novel
	var author, coverURL, description sql.NullString
	var rating sql.NullFloat64
	var lastSyncedAt sql.NullTime

	err := s.Scan(
		&n.ID, &n.ProviderID, &n.SourceURL, &n.Title, &author, &coverURL,
		&description, &n.Status, &n.Priority, &rating, &n.TotalChapters,
		&lastSyncedAt, &n.AddedAt,
	)
	if err != nil {
		return n, err
	}

	if author.Valid {
		n.Author = author.String
	}
	if coverURL.Valid {
		n.CoverURL = coverURL.String
	}
	if description.Valid {
		n.Description = description.String
	}
	if rating.Valid {
		n.Rating = rating.Float64
	}
	if lastSyncedAt.Valid {
		t := lastSyncedAt.Time
		n.LastSyncedAt = &t
	}

	return n, nil
}

func scanChapterRow(s scanner) (Chapter, error) {
	var c Chapter
	var title sql.NullString
	var readAt sql.NullTime

	err := s.Scan(&c.ID, &c.NovelID, &c.ChapterIndex, &title, &c.SourceURL, &c.IsRead, &readAt)
	if err != nil {
		return c, err
	}

	if title.Valid {
		c.Title = title.String
	}
	if readAt.Valid {
		t := readAt.Time
		c.ReadAt = &t
	}

	return c, nil
}

// GetNovelByURL retrieves a novel by its source URL.
func (db *DB) GetNovelByURL(sourceURL string) (*Novel, error) {
	query := `
		SELECT id, provider_id, source_url, title, author, cover_url, description, status, priority, rating, total_chapters, last_synced_at, added_at
		FROM novels
		WHERE source_url = ?
	`
	n, err := scanNovelRow(db.conn.QueryRow(query, sourceURL))
	if err != nil {
		if err == sql.ErrNoRows {
			return nil, nil // Not found
		}
		return nil, fmt.Errorf("failed to get novel by url: %w", err)
	}

	return &n, nil
}

// AddChapters bulk inserts chapter metadata, ignoring duplicates.
func (db *DB) AddChapters(novelID int, chapters []providers.ChapterMeta) (int, error) {
	if len(chapters) == 0 {
		return 0, nil
	}

	tx, err := db.conn.Begin()
	if err != nil {
		return 0, fmt.Errorf("failed to begin tx: %w", err)
	}
	defer tx.Rollback()

	query := `
		INSERT INTO chapters (novel_id, chapter_index, title, source_url)
		VALUES (?, ?, ?, ?)
		ON CONFLICT(novel_id, chapter_index) DO NOTHING
	`
	stmt, err := tx.Prepare(query)
	if err != nil {
		return 0, fmt.Errorf("failed to prepare stmt: %w", err)
	}
	defer stmt.Close()

	inserted := 0
	for _, c := range chapters {
		var title sql.NullString
		if c.Title != "" {
			title = sql.NullString{String: c.Title, Valid: true}
		}

		res, err := stmt.Exec(novelID, c.Index, title, c.URL)
		if err != nil {
			return 0, fmt.Errorf("failed to insert chapter %d: %w", c.Index, err)
		}
		rows, err := res.RowsAffected()
		if err == nil && rows > 0 {
			inserted++
		}
	}

	if err := tx.Commit(); err != nil {
		return 0, fmt.Errorf("failed to commit tx: %w", err)
	}

	return inserted, nil
}

// UpdateNovelSync updates the total chapters and last synced time.
func (db *DB) UpdateNovelSync(novelID int, totalChapters int) error {
	query := `
		UPDATE novels 
		SET total_chapters = ?, last_synced_at = ?
		WHERE id = ?
	`
	_, err := db.conn.Exec(query, totalChapters, time.Now().UTC(), novelID)
	if err != nil {
		return fmt.Errorf("failed to update novel sync status: %w", err)
	}
	return nil
}

// LogSync records a sync event.
func (db *DB) LogSync(novelID int, event string, detail string) error {
	query := `INSERT INTO sync_log (novel_id, event, detail) VALUES (?, ?, ?)`
	var detailNull sql.NullString
	if detail != "" {
		detailNull = sql.NullString{String: detail, Valid: true}
	}
	_, err := db.conn.Exec(query, novelID, event, detailNull)
	return err
}

// ListNovels returns all tracked novels, ordered by last read activity then title.
func (db *DB) ListNovels() ([]Novel, error) {
	query := `
		SELECT id, provider_id, source_url, title, author, cover_url, description,
		       status, priority, rating, total_chapters, last_synced_at, added_at
		FROM novels
		ORDER BY priority ASC, title ASC
	`
	rows, err := db.conn.Query(query)
	if err != nil {
		return nil, fmt.Errorf("failed to list novels: %w", err)
	}
	defer rows.Close()

	var novels []Novel
	for rows.Next() {
		n, err := scanNovelRow(rows)
		if err != nil {
			return nil, fmt.Errorf("failed to scan novel row: %w", err)
		}
		novels = append(novels, n)
	}
	return novels, rows.Err()
}

// GetNovelByID retrieves a single novel by its database ID.
func (db *DB) GetNovelByID(id int) (*Novel, error) {
	query := `
		SELECT id, provider_id, source_url, title, author, cover_url, description,
		       status, priority, rating, total_chapters, last_synced_at, added_at
		FROM novels WHERE id = ?
	`
	n, err := scanNovelRow(db.conn.QueryRow(query, id))
	if err != nil {
		if err == sql.ErrNoRows {
			return nil, nil
		}
		return nil, fmt.Errorf("failed to get novel by id: %w", err)
	}

	return &n, nil
}

// GetChaptersByNovelID retrieves all chapters for a novel, ordered by index.
func (db *DB) GetChaptersByNovelID(novelID int) ([]Chapter, error) {
	query := `
		SELECT id, novel_id, chapter_index, title, source_url, is_read, read_at
		FROM chapters
		WHERE novel_id = ?
		ORDER BY chapter_index ASC
	`
	rows, err := db.conn.Query(query, novelID)
	if err != nil {
		return nil, fmt.Errorf("failed to get chapters: %w", err)
	}
	defer rows.Close()

	var chapters []Chapter
	for rows.Next() {
		c, err := scanChapterRow(rows)
		if err != nil {
			return nil, fmt.Errorf("failed to scan chapter row: %w", err)
		}
		chapters = append(chapters, c)
	}
	return chapters, rows.Err()
}

// GetNextUnreadChapter returns the first unread chapter for a novel.
func (db *DB) GetNextUnreadChapter(novelID int) (*Chapter, error) {
	query := `
		SELECT id, novel_id, chapter_index, title, source_url, is_read, read_at
		FROM chapters
		WHERE novel_id = ? AND is_read = FALSE
		ORDER BY chapter_index ASC
		LIMIT 1
	`
	c, err := scanChapterRow(db.conn.QueryRow(query, novelID))
	if err != nil {
		if err == sql.ErrNoRows {
			return nil, nil
		}
		return nil, fmt.Errorf("failed to get next unread chapter: %w", err)
	}
	return &c, nil
}

// MarkChapterRead marks a chapter as read with the current timestamp.
func (db *DB) MarkChapterRead(chapterID int) error {
	query := `UPDATE chapters SET is_read = TRUE, read_at = ? WHERE id = ?`
	_, err := db.conn.Exec(query, time.Now().UTC(), chapterID)
	if err != nil {
		return fmt.Errorf("failed to mark chapter read: %w", err)
	}
	return nil
}

// SaveReadingPosition persists the reader's scroll offset for a chapter.
func (db *DB) SaveReadingPosition(novelID, chapterID, scrollOffset int) error {
	query := `
		INSERT INTO reading_history (novel_id, chapter_id, scroll_offset, last_read_at)
		VALUES (?, ?, ?, ?)
		ON CONFLICT(novel_id, chapter_id) DO UPDATE SET
			scroll_offset = excluded.scroll_offset,
			last_read_at  = excluded.last_read_at
	`
	_, err := db.conn.Exec(query, novelID, chapterID, scrollOffset, time.Now().UTC())
	if err != nil {
		return fmt.Errorf("failed to save reading position: %w", err)
	}
	return nil
}

// GetReadingPosition retrieves the last saved scroll offset for a chapter.
func (db *DB) GetReadingPosition(novelID, chapterID int) (int, error) {
	query := `SELECT scroll_offset FROM reading_history WHERE novel_id = ? AND chapter_id = ?`
	var offset int
	err := db.conn.QueryRow(query, novelID, chapterID).Scan(&offset)
	if err != nil {
		if err == sql.ErrNoRows {
			return 0, nil
		}
		return 0, fmt.Errorf("failed to get reading position: %w", err)
	}
	return offset, nil
}

// DeleteNovel removes a novel and all its chapters/history (via CASCADE).
func (db *DB) DeleteNovel(novelID int) error {
	_, err := db.conn.Exec(`DELETE FROM novels WHERE id = ?`, novelID)
	if err != nil {
		return fmt.Errorf("failed to delete novel: %w", err)
	}
	return nil
}

// GetReadProgress returns (read count, total count) for a novel.
func (db *DB) GetReadProgress(novelID int) (int, int, error) {
	query := `
		SELECT
			COUNT(*) AS total,
			COUNT(CASE WHEN is_read = TRUE THEN 1 END) AS read_count
		FROM chapters
		WHERE novel_id = ?
	`
	var total, readCount int
	err := db.conn.QueryRow(query, novelID).Scan(&total, &readCount)
	if err != nil {
		return 0, 0, fmt.Errorf("failed to get read progress: %w", err)
	}
	return readCount, total, nil
}
