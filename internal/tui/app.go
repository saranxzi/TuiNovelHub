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
	"treading/internal/tui/reader"
	"treading/internal/tui/search"

	tea "github.com/charmbracelet/bubbletea"
)

type ViewName string

const (
	ViewLibrary  ViewName = "library"
	ViewSearch   ViewName = "search"
	ViewChapters ViewName = "chapters"
	ViewReader   ViewName = "reader"
)

type App struct {
	config      *config.Config
	db          *db.DB
	syncService *sync.SyncService

	// Children views
	libraryModel  library.Model
	searchModel   search.Model
	chaptersModel chapters.Model
	readerModel   reader.Model

	// Active view
	activeView ViewName
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
		readerModel:   reader.NewModel(database, cfg),
		activeView:    ViewLibrary,
	}
}

func (a *App) Init() tea.Cmd {
	return tea.Batch(
		tea.EnterAltScreen,
		a.libraryModel.Init(),
		a.readerModel.Init(),
	)
}

func (a *App) routeToActiveView(msg tea.Msg) tea.Cmd {
	var cmd tea.Cmd
	var newModel tea.Model

	switch a.activeView {
	case ViewLibrary:
		newModel, cmd = a.libraryModel.Update(msg)
		a.libraryModel = newModel.(library.Model)
	case ViewSearch:
		newModel, cmd = a.searchModel.Update(msg)
		a.searchModel = newModel.(search.Model)
	case ViewChapters:
		newModel, cmd = a.chaptersModel.Update(msg)
		a.chaptersModel = newModel.(chapters.Model)
	case ViewReader:
		newModel, cmd = a.readerModel.Update(msg)
		a.readerModel = newModel.(reader.Model)
	}
	return cmd
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
	case syncChannelMsg:
		if msg.msg != nil {
			cmds = append(cmds, func() tea.Msg { return msg.msg })
		}
		cmds = append(cmds, listenToSync(msg.ch))
	case tuimsg.NavigateMsg:
		a.activeView = ViewName(msg.View)
		switch a.activeView {
		case ViewChapters:
			if msg.Data != nil {
				if novel, ok := msg.Data.(*db.Novel); ok {
					cmd = a.chaptersModel.LoadNovel(novel)
					cmds = append(cmds, cmd)
				} else if searchResult, ok := msg.Data.(providers.SearchResult); ok {
					novel := &db.Novel{
						ProviderID:    searchResult.ProviderID,
						SourceURL:     searchResult.URL,
						Title:         searchResult.Title,
						Author:        searchResult.Author,
						CoverURL:      searchResult.CoverURL,
						Description:   searchResult.Description,
						TotalChapters: searchResult.ChapterCount,
						Status:        "Reading",
					}
					if err := a.db.AddNovel(novel); err != nil {
						a.activeView = ViewChapters
						cmd = a.chaptersModel.LoadNovel(novel)
						cmds = append(cmds, cmd)
						cmds = append(cmds, func() tea.Msg { return err })
					} else {
						cmd = a.chaptersModel.LoadNovel(novel)
						cmds = append(cmds, cmd)

						// Trigger background sync asynchronously with progress updates
						ch := make(chan tea.Msg, 100)
						go func() {
							defer close(ch)
							err := a.syncService.SyncNovel(context.Background(), novel, func(pageChapters []providers.ChapterMeta) {
								ch <- tuimsg.SyncProgressMsg{NovelID: novel.ID}
							})
							ch <- tuimsg.SyncCompleteMsg{Novel: novel, Err: err}
						}()
						cmds = append(cmds, listenToSync(ch))
					}
				}
			}
		case ViewReader:
			if msg.Data != nil {
				if chapter, ok := msg.Data.(*db.Chapter); ok {
					cmd = a.readerModel.LoadChapter(chapter)
					cmds = append(cmds, cmd)
				}
			}
		case ViewSearch:
			cmd = a.searchModel.Init()
			cmds = append(cmds, cmd)
		case ViewLibrary:
			cmd = a.libraryModel.Init()
			cmds = append(cmds, cmd)
		}

		// Propagate window size to the newly active view immediately
		cmd = a.routeToActiveView(tea.WindowSizeMsg{Width: a.width, Height: a.height})
		cmds = append(cmds, cmd)
	}

	// Route incoming msg to active view
	cmd = a.routeToActiveView(msg)
	cmds = append(cmds, cmd)

	return a, tea.Batch(cmds...)
}

func (a *App) View() string {
	switch a.activeView {
	case ViewLibrary:
		return a.libraryModel.View()
	case ViewSearch:
		return a.searchModel.View()
	case ViewChapters:
		return a.chaptersModel.View()
	case ViewReader:
		return a.readerModel.View()
	default:
		return "Unknown view"
	}
}

type syncChannelMsg struct {
	ch  chan tea.Msg
	msg tea.Msg
}

func listenToSync(ch chan tea.Msg) tea.Cmd {
	return func() tea.Msg {
		msg, ok := <-ch
		if !ok {
			return nil
		}
		return syncChannelMsg{ch: ch, msg: msg}
	}
}
