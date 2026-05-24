package library

import (
	"fmt"
	"time"

	"treading/internal/db"
	"treading/internal/sync"
	"treading/internal/tui/components"
	tuimsg "treading/internal/tui/msg"

	"github.com/charmbracelet/bubbles/table"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
)

var (
	baseStyle = lipgloss.NewStyle().
		BorderStyle(lipgloss.NormalBorder()).
		BorderForeground(lipgloss.Color("240"))
)

// Model is the Bubbletea model for the library (home) view.
type Model struct {
	db          *db.DB
	syncService *sync.SyncService
	table       table.Model
	novels      []db.Novel // Keep the full list to map selected row → novel
	statusBar   *components.StatusBar
	width       int
	height      int
	err         error
}

// NewModel creates a ready-to-use library view.
func NewModel(database *db.DB, syncSvc *sync.SyncService) Model {
	columns := []table.Column{
		{Title: "Title", Width: 40},
		{Title: "Author", Width: 20},
		{Title: "Progress", Width: 15},
		{Title: "Status", Width: 15},
		{Title: "Last Synced", Width: 15},
	}

	t := table.New(
		table.WithColumns(columns),
		table.WithFocused(true),
		table.WithHeight(10),
	)

	s := table.DefaultStyles()
	s.Header = s.Header.
		BorderStyle(lipgloss.NormalBorder()).
		BorderForeground(lipgloss.Color("240")).
		BorderBottom(true).
		Bold(false)
	s.Selected = s.Selected.
		Foreground(lipgloss.Color("229")).
		Background(lipgloss.Color("57")).
		Bold(false)
	t.SetStyles(s)

	return Model{
		db:          database,
		syncService: syncSvc,
		table:       t,
		statusBar:   components.NewStatusBar(),
	}
}

func (m Model) Init() tea.Cmd {
	return m.loadNovels()
}

func (m Model) Update(incoming tea.Msg) (tea.Model, tea.Cmd) {
	var cmd tea.Cmd

	switch tmsg := incoming.(type) {
	case tea.WindowSizeMsg:
		m.width = tmsg.Width
		m.height = tmsg.Height

		h := m.height - 4
		if h < 0 {
			h = 0
		}
		m.table.SetHeight(h)
		m.statusBar.Width = tmsg.Width

	case tea.KeyMsg:
		switch tmsg.String() {
		case "q":
			return m, tea.Quit
		case "a":
			// Navigate to search view to add a novel
			return m, func() tea.Msg {
				return tuimsg.NavigateMsg{View: "search"}
			}
		case "d", "x", "delete":
			idx := m.table.Cursor()
			if idx >= 0 && idx < len(m.novels) {
				novel := m.novels[idx]
				err := m.db.DeleteNovel(novel.ID)
				if err != nil {
					m.err = err
					return m, nil
				}
				return m, m.loadNovels()
			}
		case "enter":
			// Navigate to chapter list for the selected novel
			idx := m.table.Cursor()
			if idx >= 0 && idx < len(m.novels) {
				novel := m.novels[idx]
				return m, func() tea.Msg {
					return tuimsg.NavigateMsg{
						View: "chapters",
						Data: &novel,
					}
				}
			}
		}

	case error:
		m.err = tmsg

	case novelsLoadedMsg:
		m.novels = tmsg.novels
		m.table.SetRows(tmsg.rows)
		m.statusBar.ItemCount = len(tmsg.rows)
	}

	m.table, cmd = m.table.Update(incoming)
	return m, cmd
}

func (m Model) View() string {
	if m.err != nil {
		return fmt.Sprintf("Error: %v\nPress q to quit.", m.err)
	}

	title := lipgloss.NewStyle().
		Foreground(lipgloss.Color("205")).Bold(true).
		Render(" TReading Hub Library ")

	help := lipgloss.NewStyle().
		Foreground(lipgloss.Color("240")).
		Render("  a: add novel • enter: view chapters • d/x: delete • q: quit")

	tableView := baseStyle.Render(m.table.View())

	return lipgloss.JoinVertical(lipgloss.Left,
		title,
		tableView,
		help,
		m.statusBar.View(),
	)
}

// novelsLoadedMsg carries both the raw novel slice and preformatted table rows.
type novelsLoadedMsg struct {
	novels []db.Novel
	rows   []table.Row
}

// loadNovels fetches all tracked novels from the database.
func (m Model) loadNovels() tea.Cmd {
	return func() tea.Msg {
		novels, err := m.db.ListNovels()
		if err != nil {
			return err
		}

		var rows []table.Row
		for _, n := range novels {
			readCount, total, err := m.db.GetReadProgress(n.ID)
			progress := "0/0"
			if err == nil {
				progress = fmt.Sprintf("%d/%d", readCount, total)
			}

			lastSynced := "Never"
			if n.LastSyncedAt != nil {
				lastSynced = formatTimeAgo(*n.LastSyncedAt)
			}

			rows = append(rows, table.Row{
				n.Title,
				n.Author,
				progress,
				n.Status,
				lastSynced,
			})
		}
		return novelsLoadedMsg{novels: novels, rows: rows}
	}
}

// formatTimeAgo returns a human-friendly relative timestamp.
func formatTimeAgo(t time.Time) string {
	d := time.Since(t)
	switch {
	case d < time.Minute:
		return "just now"
	case d < time.Hour:
		return fmt.Sprintf("%dm ago", int(d.Minutes()))
	case d < 24*time.Hour:
		return fmt.Sprintf("%dh ago", int(d.Hours()))
	default:
		return fmt.Sprintf("%dd ago", int(d.Hours()/24))
	}
}
