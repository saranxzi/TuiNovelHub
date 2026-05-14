package components

import (
	"fmt"

	"github.com/charmbracelet/lipgloss"
)

var statusBarStyle = lipgloss.NewStyle().
	Foreground(lipgloss.Color("#D1D1D1")).
	Background(lipgloss.Color("#2A2A2A")).
	Padding(0, 1)

type StatusBar struct {
	ViewName   string
	SyncStatus string
	ItemCount  int
	Width      int
}

func NewStatusBar() *StatusBar {
	return &StatusBar{
		ViewName:   "Library",
		SyncStatus: "Idle",
	}
}

func (s *StatusBar) View() string {
	left := fmt.Sprintf("[%s] %d items", s.ViewName, s.ItemCount)
	right := fmt.Sprintf("Sync: %s | ? Help", s.SyncStatus)

	// Calculate spacing
	w := lipgloss.Width(left) + lipgloss.Width(right)
	spaces := ""
	if s.Width > w {
		for i := 0; i < s.Width-w-2; i++ {
			spaces += " "
		}
	}

	content := left + spaces + right
	return statusBarStyle.Width(s.Width).Render(content)
}
