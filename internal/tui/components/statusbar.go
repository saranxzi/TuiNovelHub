package components

import (
	"fmt"
	"strings"

	"github.com/charmbracelet/lipgloss"
)

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
	var spaces string
	if s.Width > w {
		spaces = strings.Repeat(" ", s.Width-w-2)
	}

	content := left + spaces + right
	return StatusBarStyle.Width(s.Width).Render(content)
}
