package search

import (
	"context"
	"fmt"

	"treading/internal/providers"
	"treading/internal/tui/components"
	tuimsg "treading/internal/tui/msg"

	"github.com/charmbracelet/bubbles/list"
	"github.com/charmbracelet/bubbles/spinner"
	"github.com/charmbracelet/bubbles/textinput"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
)

// item wraps a provider SearchResult so it satisfies the list.Item interface.
type item struct {
	result providers.SearchResult
}

func (i item) Title() string {
	return i.result.Title
}

func (i item) Description() string {
	return fmt.Sprintf("by %s  •  %d chapters", i.result.Author, i.result.ChapterCount)
}

func (i item) FilterValue() string { return i.result.Title }

// Model is the Bubbletea model for the search view.
type Model struct {
	input      textinput.Model
	list       list.Model
	spinner    spinner.Model
	statusBar  *components.StatusBar
	searching  bool
	err        error
	width      int
	height     int
	providerID string
}

// NewModel creates a new, ready-to-use search view.
func NewModel() Model {
	ti := textinput.New()
	ti.Placeholder = "Search for a novel..."
	ti.Focus()
	ti.CharLimit = 156
	ti.Width = 40

	l := list.New([]list.Item{}, list.NewDefaultDelegate(), 0, 0)
	l.Title = "Search Results"
	l.SetShowStatusBar(false)
	l.SetFilteringEnabled(false)

	var providerID string
	all := providers.All()
	if len(all) > 0 {
		providerID = all[0].ID()
	} else {
		providerID = "novelfire"
	}

	return Model{
		input:      ti,
		list:       l,
		spinner:    components.NewSpinner(),
		statusBar:  components.NewStatusBar(),
		providerID: providerID,
	}
}

func (m Model) Init() tea.Cmd {
	return textinput.Blink
}

func (m Model) Update(incoming tea.Msg) (tea.Model, tea.Cmd) {
	var cmds []tea.Cmd
	var cmd tea.Cmd

	switch tmsg := incoming.(type) {
	case tea.WindowSizeMsg:
		m.width = tmsg.Width
		m.height = tmsg.Height
		m.list.SetSize(tmsg.Width, tmsg.Height-6)
		m.statusBar.Width = tmsg.Width

	case tea.KeyMsg:
		switch tmsg.String() {
		case "esc":
			if !m.input.Focused() {
				m.input.Focus()
				return m, nil
			}
			return m, func() tea.Msg {
				return tuimsg.NavigateMsg{View: "library"}
			}
		case "enter":
			if m.input.Focused() && m.input.Value() != "" {
				m.searching = true
				m.list.SetItems([]list.Item{})
				return m, searchCmd(m.providerID, m.input.Value())
			} else if !m.input.Focused() {
				selected := m.list.SelectedItem()
				if selected != nil {
					res := selected.(item).result
					return m, func() tea.Msg {
						return tuimsg.NavigateMsg{
							View: "chapters",
							Data: res,
						}
					}
				}
			}
		case "down", "j", "up", "k":
			if m.input.Focused() && len(m.list.Items()) > 0 {
				m.input.Blur()
			}
		case "tab":
			all := providers.All()
			if len(all) > 1 {
				idx := -1
				for i, p := range all {
					if p.ID() == m.providerID {
						idx = i
						break
					}
				}
				nextIdx := (idx + 1) % len(all)
				m.providerID = all[nextIdx].ID()
			}
		}

	case tuimsg.SearchResultsMsg:
		m.searching = false
		if tmsg.Err != nil {
			m.err = tmsg.Err
			return m, nil
		}
		var items []list.Item
		for _, r := range tmsg.Results {
			items = append(items, item{result: r})
		}
		m.list.SetItems(items)
		m.input.Blur()
		m.err = nil
	}

	// Delegate updates to the focused sub-component.
	if m.input.Focused() {
		m.input, cmd = m.input.Update(incoming)
		cmds = append(cmds, cmd)
	} else {
		m.list, cmd = m.list.Update(incoming)
		cmds = append(cmds, cmd)
	}

	if m.searching {
		m.spinner, cmd = m.spinner.Update(incoming)
		cmds = append(cmds, cmd)
	}

	return m, tea.Batch(cmds...)
}

func (m Model) View() string {
	var body string

	if m.err != nil {
		body = lipgloss.NewStyle().Foreground(lipgloss.Color("204")).
			Render(fmt.Sprintf("Error: %v", m.err))
	} else if m.searching {
		body = fmt.Sprintf("%s Searching %s...", m.spinner.View(), m.providerID)
	} else {
		body = m.list.View()
	}

	providerInfo := lipgloss.NewStyle().Foreground(lipgloss.Color("240")).
		Render(fmt.Sprintf("[Provider: %s  (Tab to switch)]", m.providerID))

	return lipgloss.JoinVertical(lipgloss.Left,
		m.input.View(),
		providerInfo,
		body,
		m.statusBar.View(),
	)
}

// searchCmd fires an async search against the given provider.
func searchCmd(providerID, query string) tea.Cmd {
	return func() tea.Msg {
		p, ok := providers.Get(providerID)
		if !ok {
			return tuimsg.SearchResultsMsg{
				Err: fmt.Errorf("provider %q not registered", providerID),
			}
		}

		res, err := p.Search(context.Background(), query, 1)
		return tuimsg.SearchResultsMsg{Results: res, Err: err}
	}
}
