package sync

import (
	"context"
	"fmt"
	"log"

	"treading/internal/db"
	"treading/internal/providers"
)

// SyncService orchestrates updates between providers and the database.
type SyncService struct {
	db *db.DB
}

// NewSyncService creates a new SyncService.
func NewSyncService(database *db.DB) *SyncService {
	return &SyncService{db: database}
}

// TrackNovelFromSearch creates a novel record from a search result and immediately syncs it.
func (s *SyncService) TrackNovelFromSearch(ctx context.Context, result providers.SearchResult) (*db.Novel, error) {
	novel := &db.Novel{
		ProviderID:  result.ProviderID,
		SourceURL:   result.URL,
		Title:       result.Title,
		Author:      result.Author,
		CoverURL:    result.CoverURL,
		Description: result.Description,
		Status:      "Reading",
	}

	if err := s.db.AddNovel(novel); err != nil {
		return nil, fmt.Errorf("failed to track novel: %w", err)
	}

	if err := s.SyncNovel(ctx, novel, nil); err != nil {
		return novel, fmt.Errorf("novel tracked but initial sync failed: %w", err)
	}

	return novel, nil
}

// SyncNovel pulls the latest chapters from the provider and updates the database.
func (s *SyncService) SyncNovel(ctx context.Context, novel *db.Novel, onProgress func([]providers.ChapterMeta)) error {
	p, ok := providers.Get(novel.ProviderID)
	if !ok {
		return fmt.Errorf("provider %q not found", novel.ProviderID)
	}

	chapters, err := p.GetChapterList(ctx, novel.SourceURL, func(pageChapters []providers.ChapterMeta) {
		if len(pageChapters) > 0 {
			_, _ = s.db.AddChapters(novel.ID, pageChapters)
		}
		if onProgress != nil {
			onProgress(pageChapters)
		}
	})
	if err != nil {
		s.db.LogSync(novel.ID, "sync_failed", err.Error())
		return fmt.Errorf("failed to fetch chapters for %s: %w", novel.Title, err)
	}

	if len(chapters) == 0 {
		return nil
	}

	inserted, err := s.db.AddChapters(novel.ID, chapters)
	if err != nil {
		s.db.LogSync(novel.ID, "sync_db_error", err.Error())
		return fmt.Errorf("failed to add chapters to db: %w", err)
	}

	totalChapters := len(chapters)
	if err := s.db.UpdateNovelSync(novel.ID, totalChapters); err != nil {
		s.db.LogSync(novel.ID, "sync_update_error", err.Error())
		return fmt.Errorf("failed to update novel sync status: %w", err)
	}

	s.db.LogSync(novel.ID, "sync_success", fmt.Sprintf("Synced %d chapters (%d new)", totalChapters, inserted))
	return nil
}

// SyncAll synchronizes every tracked novel in the database.
// It processes them sequentially, logging errors but continuing to the next novel.
func (s *SyncService) SyncAll(ctx context.Context) error {
	novels, err := s.db.ListNovels()
	if err != nil {
		return fmt.Errorf("failed to list novels for sync: %w", err)
	}

	var syncErrors int
	for i := range novels {
		select {
		case <-ctx.Done():
			return ctx.Err()
		default:
		}

		if err := s.SyncNovel(ctx, &novels[i], nil); err != nil {
			log.Printf("sync error for %q: %v", novels[i].Title, err)
			syncErrors++
		}
	}

	if syncErrors > 0 {
		return fmt.Errorf("sync completed with %d errors out of %d novels", syncErrors, len(novels))
	}
	return nil
}
