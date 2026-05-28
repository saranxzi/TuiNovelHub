# TReading Hub

TReading Hub is a terminal user interface (TUI) application written in Go for tracking and reading web novels. It allows users to search for novels, track reading progress, and read novel content in a clean, customizable reader view directly from the terminal.

## Features

- Terminal user interface built with Bubble Tea.
- Search and download web novels from online providers.
- Local SQLite database to persist novel metadata, chapter lists, and reading history.
- Background incremental synchronization to fetch and download chapters dynamically.
- Customizable reader view with adjustable text width, text wrapping, and alignment.
- Graceful context cancellation on background tasks to avoid resource leaks.

## Requirements

- Go 1.21 or later
- SQLite

## Setup and Running

1. Clone the repository:
   ```bash
   git clone https://github.com/saranxzi/TuiNovelHub.git
   cd TuiNovelHub
   ```

2. Build the application:
   ```bash
   go build -o treading.exe ./cmd/treading
   ```

3. Run the application:
   ```bash
   ./treading.exe
   ```

## Controls

### Library View
- a: Search and add a new novel.
- enter: View the chapter list of the selected novel.
- d / x / delete: Remove the selected novel and its chapters from the database.
- q / ctrl+c: Quit the application.

### Chapters View
- esc: Return to the Library view.
- r: Mark the selected chapter as read/unread.
- enter: Open the selected chapter in the Reader view.

### Reader View
- esc / backspace: Return to the Chapters view.
- left / p: Navigate to the previous chapter.
- right / n: Navigate to the next chapter.
- [: Decrease the maximum text line width.
- ]: Increase the maximum text line width.
- \: Toggle text centering on/off.
