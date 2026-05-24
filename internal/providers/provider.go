package providers

import "context"

// SearchResult is returned from a provider's Search method.
type SearchResult struct {
	Title        string
	Author       string
	URL          string
	CoverURL     string
	ChapterCount int
	Description  string
	ProviderID   string
}

// ChapterMeta is a lightweight chapter descriptor (no content).
type ChapterMeta struct {
	Index int
	Title string
	URL   string
}

// ChapterContent is the fully scraped, cleaned chapter ready to display.
type ChapterContent struct {
	Title        string
	MarkdownText string // Clean wrapped text. No HTML. No ads. No nav.
}

// Provider is the contract every source must satisfy.
// Implementations live in subdirectories under providers/.
type Provider interface {
	// ID returns the stable machine identifier (e.g. "novelfire").
	ID() string
	// DisplayName returns the human-readable name (e.g. "NovelFire").
	DisplayName() string
	// Search queries the source and returns paginated results.
	Search(ctx context.Context, query string, page int) ([]SearchResult, error)
	// GetChapterList returns all chapter metadata for a given novel URL.
	GetChapterList(ctx context.Context, novelURL string, onProgress func([]ChapterMeta)) ([]ChapterMeta, error)
	// GetChapterContent scrapes and returns clean Markdown for one chapter.
	GetChapterContent(ctx context.Context, chapterURL string) (ChapterContent, error)
}
