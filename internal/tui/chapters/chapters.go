package chapters

import (
	"fmt"

	"treading/internal/db"
	"treading/internal/sync"
	"treading/internal/tui/components"
	tuimsg "treading/internal/tui/msg"

	"github.com/charmbracelet/bubbles/list"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
)

// item wraps a db.Chapter so it satisfies list.Item.
type item struct {
	chapter db.Chapter
}

func (i item) Title() string {
	prefix := "  "
	if i.chapter.IsRead {
		prefix = "✓ "
	}
	return fmt.Sprintf("%s Chapter %d: %s", prefix, i.chapter.ChapterIndex, i.chapter.Title)
}

func (i item) Description() string {
	if i.chapter.IsRead && i.chapter.ReadAt != nil {
		return "Read " + i.chapter.ReadAt.Format("2006-01-02 15:04")
	}
	return "Unread"
}

func (i item) FilterValue() string { return i.chapter.Title }

// chaptersLoadedMsg is a private message carrying the loaded items.
type chaptersLoadedMsg struct {
	items []list.Item
}

// Model is the Bubbletea model for the chapter-list view.
type Model struct {
	novel       *db.Novel
	db          *db.DB
	syncService *sync.SyncService
	list        list.Model
	statusBar   *components.StatusBar
	width       int
	height      int
	err         error
}

// NewModel creates a ready-to-use chapter list view.
func NewModel(database *db.DB, syncSvc *sync.SyncService) Model {
	l := list.New([]list.Item{}, list.NewDefaultDelegate(), 0, 0)
	l.Title = "Chapters"
	l.SetShowStatusBar(false)

	return Model{
		db:          database,
		syncService: syncSvc,
		list:        l,
		statusBar:   components.NewStatusBar(),
	}
}

func (m Model) Init() tea.Cmd {
	return nil
}

// LoadNovel populates the view with a specific novel's chapters.
func (m *Model) LoadNovel(novel *db.Novel) tea.Cmd {
	m.novel = novel
	m.list.Title = "Chapters — " + novel.Title
	
	chaps, err := m.db.GetChaptersByNovelID(novel.ID)
	if err == nil && len(chaps) == 0 {
		m.statusBar.SyncStatus = "Syncing..."
	} else {
		m.statusBar.SyncStatus = "Idle"
	}
	return m.loadChapters()
}

func (m Model) Update(incoming tea.Msg) (tea.Model, tea.Cmd) {
	var cmd tea.Cmd
	var cmds []tea.Cmd

	switch tmsg := incoming.(type) {
	case tea.WindowSizeMsg:
		m.width = tmsg.Width
		m.height = tmsg.Height
		m.list.SetSize(tmsg.Width, tmsg.Height-3)
		m.statusBar.Width = tmsg.Width

	case tea.KeyMsg:
		if m.list.FilterState() == list.Filtering {
			m.list, cmd = m.list.Update(incoming)
			return m, cmd
		}

		switch tmsg.String() {
		case "esc":
			return m, func() tea.Msg {
				return tuimsg.NavigateMsg{View: "library"}
			}
		case "r":
			selected := m.list.SelectedItem()
			if selected != nil {
				ch := selected.(item).chapter
				if !ch.IsRead {
					m.db.MarkChapterRead(ch.ID)
					cmds = append(cmds, m.loadChapters())
				}
			}
		case "enter":
			selected := m.list.SelectedItem()
			if selected != nil {
				ch := selected.(item).chapter
				return m, func() tea.Msg {
					return tuimsg.NavigateMsg{
						View: "reader",
						Data: &ch,
					}
				}
			}
		}

	case chaptersLoadedMsg:
		cmd = m.list.SetItems(tmsg.items)
		cmds = append(cmds, cmd)

	case tuimsg.SyncProgressMsg:
		if m.novel != nil && tmsg.NovelID == m.novel.ID {
			cmds = append(cmds, m.loadChapters())
		}

	case tuimsg.SyncCompleteMsg:
		m.statusBar.SyncStatus = "Idle"
		if tmsg.Err != nil {
			m.err = tmsg.Err
		} else {
			if m.novel != nil {
				if updated, err := m.db.GetNovelByID(m.novel.ID); err == nil && updated != nil {
					m.novel = updated
				}
			}
			cmds = append(cmds, m.loadChapters())
		}

	case error:
		m.err = tmsg
	}

	m.list, cmd = m.list.Update(incoming)
	cmds = append(cmds, cmd)

	return m, tea.Batch(cmds...)
}

func (m Model) GetNovelID() int {
	if m.novel == nil {
		return 0
	}
	return m.novel.ID
}

func (m Model) View() string {
	if m.err != nil {
		return lipgloss.NewStyle().Foreground(lipgloss.Color("204")).
			Render(fmt.Sprintf("Error: %v", m.err))
	}

	return lipgloss.JoinVertical(lipgloss.Left,
		m.list.View(),
		m.statusBar.View(),
	)
}

// loadChapters fetches all chapters for the current novel from the database.
func (m Model) loadChapters() tea.Cmd {
	return func() tea.Msg {
		if m.novel == nil {
			return nil
		}
		chaps, err := m.db.GetChaptersByNovelID(m.novel.ID)
		if err != nil {
			return err
		}

		var items []list.Item
		for _, c := range chaps {
			items = append(items, item{chapter: c})
		}
		return chaptersLoadedMsg{items: items}
	}
}
