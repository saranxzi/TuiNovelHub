package providers

var registry = map[string]Provider{}

// Register adds a provider. Called from each provider's init() function.
func Register(p Provider) {
	registry[p.ID()] = p
}

// Get retrieves a provider by ID.
func Get(id string) (Provider, bool) {
	p, ok := registry[id]
	return p, ok
}

// All returns every registered provider.
func All() []Provider {
	providers := make([]Provider, 0, len(registry))
	for _, p := range registry {
		providers = append(providers, p)
	}
	return providers
}
