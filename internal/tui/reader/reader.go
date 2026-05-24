package reader

import (
	"context"
	"fmt"

	"treading/internal/config"
	"treading/internal/db"
	"treading/internal/providers"
	"treading/internal/tui/components"
	tuimsg "treading/internal/tui/msg"

	"github.com/charmbracelet/bubbles/spinner"
	"github.com/charmbracelet/bubbles/viewport"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
)

type Model struct {
	db          *db.DB
	config      *config.Config
	novel       *db.Novel
	chapter     *db.Chapter
	chapters    []db.Chapter
	viewport    viewport.Model
	spinner     spinner.Model
	loading     bool
	err         error
	width       int
	height      int
	title       string
	content     string
}

func NewModel(database *db.DB, cfg *config.Config) Model {
	s := components.NewSpinner()
	vp := viewport.New(0, 0)
	return Model{
		db:       database,
		config:   cfg,
		spinner:  s,
		viewport: vp,
	}
}

func (m Model) Init() tea.Cmd {
	return nil
}

type chapterLoadedMsg struct {
	novel        *db.Novel
	chapter      *db.Chapter
	chapters     []db.Chapter
	content      providers.ChapterContent
	scrollOffset int
	err          error
}

func (m Model) loadChapterCmd(ch *db.Chapter) tea.Cmd {
	return func() tea.Msg {
		novel, err := m.db.GetNovelByID(ch.NovelID)
		if err != nil {
			return chapterLoadedMsg{err: err}
		}

		chaps, err := m.db.GetChaptersByNovelID(ch.NovelID)
		if err != nil {
			return chapterLoadedMsg{err: err}
		}

		p, ok := providers.Get(novel.ProviderID)
		if !ok {
			return chapterLoadedMsg{err: fmt.Errorf("provider %s not found", novel.ProviderID)}
		}

		content, err := p.GetChapterContent(context.Background(), ch.SourceURL)
		if err != nil {
			return chapterLoadedMsg{err: err}
		}

		offset, err := m.db.GetReadingPosition(novel.ID, ch.ID)
		if err != nil {
			offset = 0
		}

		// Auto-mark as read
		_ = m.db.MarkChapterRead(ch.ID)

		return chapterLoadedMsg{
			novel:        novel,
			chapter:      ch,
			chapters:     chaps,
			content:      content,
			scrollOffset: offset,
		}
	}
}

func (m *Model) LoadChapter(ch *db.Chapter) tea.Cmd {
	m.loading = true
	m.err = nil
	m.chapter = ch
	return tea.Batch(
		m.spinner.Tick,
		m.loadChapterCmd(ch),
	)
}

func (m Model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	var cmd tea.Cmd
	var cmds []tea.Cmd

	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.width = msg.Width
		m.height = msg.Height
		headerHeight := 2
		footerHeight := 2
		m.viewport.Width = msg.Width
		m.viewport.Height = msg.Height - headerHeight - footerHeight
		m.reformatContent()

	case spinner.TickMsg:
		if m.loading {
			m.spinner, cmd = m.spinner.Update(msg)
			return m, cmd
		}

	case chapterLoadedMsg:
		m.loading = false
		if msg.err != nil {
			m.err = msg.err
			return m, nil
		}

		m.novel = msg.novel
		m.chapter = msg.chapter
		m.chapters = msg.chapters
		m.title = msg.content.Title
		m.content = msg.content.MarkdownText

		m.reformatContent()
		m.viewport.YOffset = msg.scrollOffset

	case tea.KeyMsg:
		if m.loading {
			if msg.String() == "esc" || msg.String() == "q" {
				return m, func() tea.Msg {
					return tuimsg.NavigateMsg{View: "chapters", Data: m.novel}
				}
			}
			return m, nil
		}

		if m.err != nil {
			if msg.String() == "esc" || msg.String() == "q" {
				return m, func() tea.Msg {
					return tuimsg.NavigateMsg{View: "chapters", Data: m.novel}
				}
			}
			return m, nil
		}

		switch msg.String() {
		case "esc", "backspace":
			saveCmd := savePositionCmd(m.db, m.novel.ID, m.chapter.ID, m.viewport.YOffset)
			navCmd := func() tea.Msg {
				return tuimsg.NavigateMsg{View: "chapters", Data: m.novel}
			}
			return m, tea.Batch(saveCmd, navCmd)

		case "n", "right": // Next chapter
			nextCh := m.getNextChapter()
			if nextCh != nil {
				saveCmd := savePositionCmd(m.db, m.novel.ID, m.chapter.ID, m.viewport.YOffset)
				loadCmd := m.LoadChapter(nextCh)
				return m, tea.Batch(saveCmd, loadCmd)
			}

		case "p", "left": // Prev chapter
			prevCh := m.getPrevChapter()
			if prevCh != nil {
				saveCmd := savePositionCmd(m.db, m.novel.ID, m.chapter.ID, m.viewport.YOffset)
				loadCmd := m.LoadChapter(prevCh)
				return m, tea.Batch(saveCmd, loadCmd)
			}

		case "[":
			m.config.Reader.MaxLineWidth -= 5
			if m.config.Reader.MaxLineWidth < 30 {
				m.config.Reader.MaxLineWidth = 30
			}
			m.reformatContent()

		case "]":
			m.config.Reader.MaxLineWidth += 5
			if m.config.Reader.MaxLineWidth > 160 {
				m.config.Reader.MaxLineWidth = 160
			}
			m.reformatContent()

		case "\\":
			m.config.Reader.CenterText = !m.config.Reader.CenterText
			m.reformatContent()
		}
	}

	if !m.loading && m.err == nil {
		m.viewport, cmd = m.viewport.Update(msg)
		cmds = append(cmds, cmd)
	}

	return m, tea.Batch(cmds...)
}

func (m *Model) getNextChapter() *db.Chapter {
	if m.chapter == nil || len(m.chapters) == 0 {
		return nil
	}
	for i, ch := range m.chapters {
		if ch.ID == m.chapter.ID {
			if i < len(m.chapters)-1 {
				return &m.chapters[i+1]
			}
			break
		}
	}
	return nil
}

func (m *Model) getPrevChapter() *db.Chapter {
	if m.chapter == nil || len(m.chapters) == 0 {
		return nil
	}
	for i, ch := range m.chapters {
		if ch.ID == m.chapter.ID {
			if i > 0 {
				return &m.chapters[i-1]
			}
			break
		}
	}
	return nil
}

func (m *Model) reformatContent() {
	if m.content == "" {
		return
	}

	width := m.width
	if m.config.Reader.MaxLineWidth > 0 && m.config.Reader.MaxLineWidth < width {
		width = m.config.Reader.MaxLineWidth
	}

	style := lipgloss.NewStyle().Width(width)
	wrappedText := style.Render(m.content)
	
	if m.config.Reader.CenterText && m.width > width {
		leftPadding := (m.width - width) / 2
		wrappedText = lipgloss.NewStyle().PaddingLeft(leftPadding).Render(wrappedText)
	}

	m.viewport.SetContent(wrappedText)
}

func (m Model) View() string {
	if m.err != nil {
		return lipgloss.NewStyle().
			Foreground(lipgloss.Color("#F25D94")).
			Render(fmt.Sprintf("Error loading chapter:\n%v\n\nPress esc to return.", m.err))
	}

	if m.loading {
		return fmt.Sprintf("\n\n   %s Loading chapter content...\n\n   Press esc to cancel.", m.spinner.View())
	}

	novelTitle := ""
	if m.novel != nil {
		novelTitle = m.novel.Title
	}
	headerText := fmt.Sprintf(" %s  •  %s", novelTitle, m.title)
	headerStyle := lipgloss.NewStyle().
		Foreground(lipgloss.Color("#FFF")).
		Background(lipgloss.Color("#7D56F4")).
		Bold(true).
		Padding(0, 1)
	
	header := headerStyle.Width(m.width).Render(headerText)

	percent := int(m.viewport.ScrollPercent() * 100)
	centerStr := "off"
	if m.config.Reader.CenterText {
		centerStr = "on"
	}
	footerText := fmt.Sprintf(" %d%% • width: %d • center: %s • keys: esc (exit) • left/right • [ and ] (width) • \\ (center)", percent, m.config.Reader.MaxLineWidth, centerStr)
	footerStyle := lipgloss.NewStyle().
		Foreground(lipgloss.Color("#D1D1D1")).
		Background(lipgloss.Color("#2A2A2A")).
		Padding(0, 1)

	footer := footerStyle.Width(m.width).Render(footerText)

	return lipgloss.JoinVertical(lipgloss.Left,
		header,
		"",
		m.viewport.View(),
		"",
		footer,
	)
}

func savePositionCmd(database *db.DB, novelID, chapterID, offset int) tea.Cmd {
	return func() tea.Msg {
		_ = database.SaveReadingPosition(novelID, chapterID, offset)
		return nil
	}
}
