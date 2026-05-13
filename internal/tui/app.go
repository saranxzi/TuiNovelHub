package tui

import (
	"context"

	"treading/internal/config"
	"treading/internal/db"
	"treading/internal/providers"
	"treading/internal/sync"
	"treading/internal/tui/chapters"
	"treading/internal/tui/library"
	tuimsg "treading/internal/tui/msg"
	"treading/internal/tui/search"

	tea "github.com/charmbracelet/bubbletea"
)

type App struct {
	config      *config.Config
	db          *db.DB
	syncService *sync.SyncService

	// Children views
	libraryModel  tea.Model
	searchModel   tea.Model
	chaptersModel chapters.Model

	// Active view
	activeView string
	width      int
	height     int
}

func NewApp(cfg *config.Config, database *db.DB) *App {
	syncSvc := sync.NewSyncService(database)

	return &App{
		config:        cfg,
		db:            database,
		syncService:   syncSvc,
		libraryModel:  library.NewModel(database, syncSvc),
		searchModel:   search.NewModel(),
		chaptersModel: chapters.NewModel(database, syncSvc),
		activeView:    "library",
	}
}

func (a *App) Init() tea.Cmd {
	return tea.Batch(
		tea.EnterAltScreen,
		a.libraryModel.Init(),
	)
}

func (a *App) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	var cmds []tea.Cmd
	var cmd tea.Cmd

	switch msg := msg.(type) {
	case tea.KeyMsg:
		switch msg.String() {
		case "ctrl+c": // Global quit
			return a, tea.Quit
		}
	case tea.WindowSizeMsg:
		a.width = msg.Width
		a.height = msg.Height
	case tuimsg.NavigateMsg:
		a.activeView = msg.View
		if msg.View == "chapters" && msg.Data != nil {
			if novel, ok := msg.Data.(*db.Novel); ok {
				cmd = a.chaptersModel.LoadNovel(novel)
				cmds = append(cmds, cmd)
			} else if searchResult, ok := msg.Data.(providers.SearchResult); ok {
				// We came from search, track it first
				// This would be async in reality, but simplified here
				novel, err := a.syncService.TrackNovelFromSearch(context.Background(), searchResult)
				if err == nil {
					cmd = a.chaptersModel.LoadNovel(novel)
					cmds = append(cmds, cmd)
				}
			}
		}
		if msg.View == "search" {
			cmd = a.searchModel.Init()
			cmds = append(cmds, cmd)
		}
		if msg.View == "library" {
			cmd = a.libraryModel.Init()
			cmds = append(cmds, cmd)
		}
	}

	// Route msg to active view
	if a.activeView == "library" {
		a.libraryModel, cmd = a.libraryModel.Update(msg)
		cmds = append(cmds, cmd)
	} else if a.activeView == "search" {
		a.searchModel, cmd = a.searchModel.Update(msg)
		cmds = append(cmds, cmd)
	} else if a.activeView == "chapters" {
		var newModel tea.Model
		newModel, cmd = a.chaptersModel.Update(msg)
		a.chaptersModel = newModel.(chapters.Model)
		cmds = append(cmds, cmd)
	}

	return a, tea.Batch(cmds...)
}

func (a *App) View() string {
	if a.activeView == "library" {
		return a.libraryModel.View()
	} else if a.activeView == "search" {
		return a.searchModel.View()
	} else if a.activeView == "chapters" {
		return a.chaptersModel.View()
	}
	return "Unknown view"
}
