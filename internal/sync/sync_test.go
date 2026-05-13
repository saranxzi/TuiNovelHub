package sync_test

import (
	"context"
	"testing"
	"time"

	"treading/internal/db"
	"treading/internal/providers"
	_ "treading/internal/providers/novelfire" // Register providers
	"treading/internal/sync"
)

func TestSyncNovelIntegration(t *testing.T) {
	tempDir := t.TempDir()
	database, err := db.Open(tempDir)
	if err != nil {
		t.Fatalf("Failed to open database: %v", err)
	}
	defer database.Close()

	novel := &db.Novel{
		ProviderID: "novelfire",
		SourceURL:  "https://novelfire.net/book/cultivation-online",
		Title:      "Cultivation Online",
		Status:     "Reading",
		Priority:   1,
	}

	err = database.AddNovel(novel)
	if err != nil {
		t.Fatalf("Failed to add novel: %v", err)
	}
	if novel.ID == 0 {
		t.Fatalf("Expected novel ID to be set, got 0")
	}

	svc := sync.NewSyncService(database)

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	// --- First sync ---
	t.Logf("Syncing novel %s...", novel.Title)
	err = svc.SyncNovel(ctx, novel)
	if err != nil {
		t.Fatalf("SyncNovel failed: %v", err)
	}

	syncedNovel, err := database.GetNovelByURL(novel.SourceURL)
	if err != nil {
		t.Fatalf("Failed to get synced novel: %v", err)
	}
	if syncedNovel.TotalChapters == 0 {
		t.Fatalf("Expected total chapters > 0, got 0")
	}
	if syncedNovel.LastSyncedAt == nil {
		t.Fatalf("Expected last_synced_at to be set")
	}
	t.Logf("Sync complete! Total Chapters: %d", syncedNovel.TotalChapters)

	// --- Idempotent re-sync ---
	err = svc.SyncNovel(ctx, novel)
	if err != nil {
		t.Fatalf("Second SyncNovel failed: %v", err)
	}
	t.Log("Idempotency check passed.")

	// --- GetChaptersByNovelID ---
	chapters, err := database.GetChaptersByNovelID(novel.ID)
	if err != nil {
		t.Fatalf("GetChaptersByNovelID failed: %v", err)
	}
	if len(chapters) == 0 {
		t.Fatal("Expected chapters in DB, got 0")
	}
	t.Logf("Chapters in DB: %d. First: %q", len(chapters), chapters[0].Title)

	// --- MarkChapterRead ---
	err = database.MarkChapterRead(chapters[0].ID)
	if err != nil {
		t.Fatalf("MarkChapterRead failed: %v", err)
	}

	readCount, total, err := database.GetReadProgress(novel.ID)
	if err != nil {
		t.Fatalf("GetReadProgress failed: %v", err)
	}
	if readCount != 1 {
		t.Fatalf("Expected 1 read chapter, got %d", readCount)
	}
	t.Logf("Read progress: %d / %d", readCount, total)

	// --- GetNextUnreadChapter ---
	next, err := database.GetNextUnreadChapter(novel.ID)
	if err != nil {
		t.Fatalf("GetNextUnreadChapter failed: %v", err)
	}
	if next == nil {
		t.Fatal("Expected a next unread chapter, got nil")
	}
	if next.ChapterIndex <= chapters[0].ChapterIndex {
		t.Fatalf("Next unread chapter index (%d) should be > first chapter (%d)", next.ChapterIndex, chapters[0].ChapterIndex)
	}
	t.Logf("Next unread: Ch%d %q", next.ChapterIndex, next.Title)

	// --- SaveReadingPosition / GetReadingPosition ---
	err = database.SaveReadingPosition(novel.ID, chapters[0].ID, 42)
	if err != nil {
		t.Fatalf("SaveReadingPosition failed: %v", err)
	}
	offset, err := database.GetReadingPosition(novel.ID, chapters[0].ID)
	if err != nil {
		t.Fatalf("GetReadingPosition failed: %v", err)
	}
	if offset != 42 {
		t.Fatalf("Expected scroll offset 42, got %d", offset)
	}
	t.Log("Reading position save/load passed.")

	// --- ListNovels ---
	novels, err := database.ListNovels()
	if err != nil {
		t.Fatalf("ListNovels failed: %v", err)
	}
	if len(novels) != 1 {
		t.Fatalf("Expected 1 novel in list, got %d", len(novels))
	}
	t.Logf("ListNovels: %q (%d chapters)", novels[0].Title, novels[0].TotalChapters)

	// --- GetNovelByID ---
	byID, err := database.GetNovelByID(novel.ID)
	if err != nil {
		t.Fatalf("GetNovelByID failed: %v", err)
	}
	if byID == nil || byID.Title != novel.Title {
		t.Fatalf("GetNovelByID returned wrong novel")
	}

	// --- DeleteNovel ---
	err = database.DeleteNovel(novel.ID)
	if err != nil {
		t.Fatalf("DeleteNovel failed: %v", err)
	}
	deleted, _ := database.GetNovelByID(novel.ID)
	if deleted != nil {
		t.Fatal("Expected novel to be deleted")
	}
	t.Log("Delete cascade passed.")
}

func TestTrackNovelFromSearch(t *testing.T) {
	tempDir := t.TempDir()
	database, err := db.Open(tempDir)
	if err != nil {
		t.Fatalf("Failed to open database: %v", err)
	}
	defer database.Close()

	svc := sync.NewSyncService(database)

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	result := providers.SearchResult{
		Title:      "Cultivation Online",
		URL:        "https://novelfire.net/book/cultivation-online",
		ProviderID: "novelfire",
	}

	novel, err := svc.TrackNovelFromSearch(ctx, result)
	if err != nil {
		t.Fatalf("TrackNovelFromSearch failed: %v", err)
	}
	if novel.ID == 0 {
		t.Fatal("Expected novel ID")
	}
	if novel.TotalChapters > 0 {
		// novel struct isn't refreshed, check from DB
	}

	fromDB, err := database.GetNovelByURL(result.URL)
	if err != nil || fromDB == nil {
		t.Fatalf("Novel not persisted: %v", err)
	}
	if fromDB.TotalChapters == 0 {
		t.Fatal("Expected chapters to be synced")
	}
	t.Logf("TrackNovelFromSearch: %q with %d chapters", fromDB.Title, fromDB.TotalChapters)
}
