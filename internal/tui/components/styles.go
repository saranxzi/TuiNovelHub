package components

import "github.com/charmbracelet/lipgloss"

var (
	// Base Colors
	PrimaryColor   = lipgloss.Color("#7D56F4") // Purple
	SecondaryColor = lipgloss.Color("#2A2A2A") // Dark Grey
	TextColor      = lipgloss.Color("#D1D1D1") // Light Grey
	DimTextColor   = lipgloss.Color("#6A6A6A") // Dim Grey
	SuccessColor   = lipgloss.Color("#43BF6D") // Green
	ErrorColor     = lipgloss.Color("#F25D94") // Pink/Red
	WarningColor   = lipgloss.Color("#F3FF69") // Yellow
	BorderColor    = lipgloss.Color("#3C3C3C")

	// Base Styles
	BaseStyle = lipgloss.NewStyle().Foreground(TextColor)

	TitleStyle = lipgloss.NewStyle().
			Foreground(lipgloss.Color("#FFF")).
			Background(PrimaryColor).
			Padding(0, 1)

	DimStyle = lipgloss.NewStyle().Foreground(DimTextColor)

	HighlightStyle = lipgloss.NewStyle().Foreground(PrimaryColor)

	StatusBarStyle = lipgloss.NewStyle().
			Foreground(TextColor).
			Background(SecondaryColor).
			Padding(0, 1)

	ListSelectedStyle = lipgloss.NewStyle().
			Border(lipgloss.NormalBorder(), false, false, false, true).
			BorderForeground(PrimaryColor).
			Foreground(PrimaryColor).
			Padding(0, 1)

	ListNormalStyle = lipgloss.NewStyle().
			Padding(0, 1).
			PaddingLeft(2)

	HelpKeyStyle  = lipgloss.NewStyle().Foreground(PrimaryColor).Bold(true)
	HelpDescStyle = lipgloss.NewStyle().Foreground(DimTextColor)
)
