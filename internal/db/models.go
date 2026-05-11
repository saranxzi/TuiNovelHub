package db

import (
	"time"
)

// Novel represents a tracked novel in the database.
type Novel struct {
	ID            int
	ProviderID    string
	SourceURL     string
	Title         string
	Author        string
	CoverURL      string
	Description   string
	Status        string
	Priority      int
	Rating        float64
	TotalChapters int
	LastSyncedAt  *time.Time
	AddedAt       time.Time
}

// Chapter represents a chapter's metadata in the database.
type Chapter struct {
	ID           int
	NovelID      int
	ChapterIndex int
	Title        string
	SourceURL    string
	IsRead       bool
	ReadAt       *time.Time
}
