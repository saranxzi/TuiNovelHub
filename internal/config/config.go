package config

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/BurntSushi/toml"
)

type AppConfig struct {
	DataDir string `toml:"data_dir"`
	Theme   string `toml:"theme"`
}

type ReaderConfig struct {
	MaxLineWidth int  `toml:"max_line_width"`
	CenterText   bool `toml:"center_text"`
}

type Config struct {
	App    AppConfig    `toml:"app"`
	Reader ReaderConfig `toml:"reader"`
}

func DefaultConfig() Config {
	return Config{
		App: AppConfig{
			DataDir: "~/.local/share/treading",
			Theme:   "dark",
		},
		Reader: ReaderConfig{
			MaxLineWidth: 80,
			CenterText:   true,
		},
	}
}

// Save writes the config back to disk.
func (c *Config) Save() error {
	home, err := os.UserHomeDir()
	if err != nil {
		return fmt.Errorf("could not get home dir: %w", err)
	}

	configDir := filepath.Join(home, ".config", "treading")
	configPath := filepath.Join(configDir, "config.toml")

	f, err := os.Create(configPath)
	if err != nil {
		return fmt.Errorf("failed to create config file: %w", err)
	}
	defer f.Close()

	encoder := toml.NewEncoder(f)
	if err := encoder.Encode(c); err != nil {
		return fmt.Errorf("failed to encode config: %w", err)
	}
	return nil
}

// Load reads the config from disk, or creates it with defaults if it doesn't exist.
func Load() (*Config, error) {
	home, err := os.UserHomeDir()
	if err != nil {
		return nil, fmt.Errorf("could not get home dir: %w", err)
	}

	configDir := filepath.Join(home, ".config", "treading")
	configPath := filepath.Join(configDir, "config.toml")

	// Ensure config dir exists
	if err := os.MkdirAll(configDir, 0755); err != nil {
		return nil, fmt.Errorf("failed to create config dir: %w", err)
	}

	cfg := DefaultConfig()

	if _, err := os.Stat(configPath); os.IsNotExist(err) {
		// Create default config
		f, err := os.Create(configPath)
		if err != nil {
			return nil, fmt.Errorf("failed to create default config: %w", err)
		}
		defer f.Close()

		encoder := toml.NewEncoder(f)
		if err := encoder.Encode(cfg); err != nil {
			return nil, fmt.Errorf("failed to encode default config: %w", err)
		}
		fmt.Printf("Notice: Created default configuration at %s\n", configPath)
	} else {
		// Load existing
		if _, err := toml.DecodeFile(configPath, &cfg); err != nil {
			return nil, fmt.Errorf("failed to decode config: %w", err)
		}
	}

	// Handle ~ in DataDir
	if strings.HasPrefix(cfg.App.DataDir, "~") {
		cfg.App.DataDir = filepath.Join(home, cfg.App.DataDir[1:])
	}

	// Ensure data dir exists
	if err := os.MkdirAll(cfg.App.DataDir, 0755); err != nil {
		return nil, fmt.Errorf("failed to create data dir: %w", err)
	}

	return &cfg, nil
}
