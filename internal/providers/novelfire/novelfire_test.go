package novelfire

import (
	"context"
	"testing"
	"time"

	"treading/internal/providers"
)

func TestNovelFirePipeline(t *testing.T) {
	p, ok := providers.Get("novelfire")
	if !ok {
		t.Fatalf("novelfire provider not registered")
	}

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	t.Log("Searching for 'cultivation'...")
	results, err := p.Search(ctx, "cultivation", 1)
	if err != nil {
		t.Fatalf("Search failed: %v", err)
	}

	if len(results) == 0 {
		t.Fatalf("Expected at least 1 search result, got 0")
	}
	t.Logf("Found %d results. First result: %s (%s)", len(results), results[0].Title, results[0].URL)

	firstResult := results[0]

	t.Logf("Fetching chapter list for %s...", firstResult.URL)
	chapters, err := p.GetChapterList(ctx, firstResult.URL)
	if err != nil {
		t.Fatalf("GetChapterList failed: %v", err)
	}

	if len(chapters) == 0 {
		t.Fatalf("Expected at least 1 chapter, got 0")
	}
	t.Logf("Found %d chapters. First chapter: %s (%s)", len(chapters), chapters[0].Title, chapters[0].URL)

	firstChapter := chapters[0]

	t.Logf("Fetching chapter content for %s...", firstChapter.URL)
	content, err := p.GetChapterContent(ctx, firstChapter.URL)
	if err != nil {
		t.Fatalf("GetChapterContent failed: %v", err)
	}

	if content.MarkdownText == "" {
		t.Fatalf("Expected non-empty markdown content, got empty string")
	}

	t.Logf("Chapter content fetched successfully. Length: %d characters", len(content.MarkdownText))
}
