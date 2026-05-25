package msg

import (
	"treading/internal/db"
	"treading/internal/providers"
)

// NavigateMsg is used to transition between views.
type NavigateMsg struct {
	View string
	Data interface{}
}

// SearchResultsMsg carries search results back to the search view.
type SearchResultsMsg struct {
	Results []providers.SearchResult
	Err     error
}

// SyncCompleteMsg indicates a novel has finished syncing its chapters.
type SyncCompleteMsg struct {
	Novel *db.Novel
	Err   error
}

// SyncProgressMsg indicates that progress has been made during a sync operation.
type SyncProgressMsg struct {
	NovelID int
}

// NovelDeletedMsg indicates a novel has been deleted.
type NovelDeletedMsg struct {
	NovelID int
}
