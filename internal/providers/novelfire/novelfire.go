package novelfire

import (
	"context"
	"fmt"
	"strconv"
	"strings"
	"time"

	md "github.com/JohannesKaufmann/html-to-markdown"
	"github.com/PuerkitoBio/goquery"
	"github.com/go-resty/resty/v2"
	"golang.org/x/time/rate"

	"treading/internal/providers"
)

func init() {
	client := resty.New().
		SetBaseURL("https://novelfire.net").
		SetRetryCount(5).
		SetRetryWaitTime(2 * time.Second).
		SetRetryMaxWaitTime(60 * time.Second).
		SetHeader("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

	providers.Register(&NovelFireProvider{
		client:  client,
		limiter: rate.NewLimiter(rate.Every(2*time.Second), 1),
	})
}

type NovelFireProvider struct {
	client  *resty.Client
	limiter *rate.Limiter
}

func (p *NovelFireProvider) ID() string          { return "novelfire" }
func (p *NovelFireProvider) DisplayName() string { return "NovelFire" }

func (p *NovelFireProvider) Search(ctx context.Context, query string, page int) ([]providers.SearchResult, error) {
	if err := p.limiter.Wait(ctx); err != nil {
		return nil, err
	}

	resp, err := p.client.R().
		SetContext(ctx).
		SetQueryParams(map[string]string{
			"keyword": query,
			"page":    strconv.Itoa(page),
		}).
		Get("/search")

	if err != nil {
		return nil, fmt.Errorf("search request failed: %w", err)
	}

	if resp.IsError() {
		return nil, fmt.Errorf("search returned error status: %s", resp.Status())
	}

	doc, err := goquery.NewDocumentFromReader(strings.NewReader(resp.String()))
	if err != nil {
		return nil, fmt.Errorf("failed to parse search HTML: %w", err)
	}

	var results []providers.SearchResult

	doc.Find("li.novel-item").Each(func(i int, sel *goquery.Selection) {
		aTag := sel.Find("a").First()
		novelURL := aTag.AttrOr("href", "")
		if novelURL != "" && strings.HasPrefix(novelURL, "/") {
			novelURL = "https://novelfire.net" + novelURL
		}

		title := aTag.AttrOr("title", sel.Find(".novel-title").Text())
		title = strings.TrimSpace(title)

		coverURL := sel.Find("img").AttrOr("data-src", sel.Find("img").AttrOr("src", ""))
		if coverURL != "" && strings.HasPrefix(coverURL, "/") {
			coverURL = "https://novelfire.net" + coverURL
		}

		results = append(results, providers.SearchResult{
			Title:      title,
			URL:        novelURL,
			CoverURL:   coverURL,
			ProviderID: p.ID(),
		})
	})

	return results, nil
}

func (p *NovelFireProvider) GetChapterList(ctx context.Context, novelURL string) ([]providers.ChapterMeta, error) {
	if err := p.limiter.Wait(ctx); err != nil {
		return nil, err
	}

	chaptersURL := novelURL
	if !strings.HasSuffix(chaptersURL, "/chapters") {
		chaptersURL = strings.TrimSuffix(chaptersURL, "/") + "/chapters"
	}

	resp, err := p.client.R().
		SetContext(ctx).
		Get(chaptersURL)

	if err != nil {
		return nil, fmt.Errorf("chapters request failed: %w", err)
	}

	if resp.IsError() {
		return nil, fmt.Errorf("chapters returned error status: %s", resp.Status())
	}

	doc, err := goquery.NewDocumentFromReader(strings.NewReader(resp.String()))
	if err != nil {
		return nil, fmt.Errorf("failed to parse chapters HTML: %w", err)
	}

	var chapters []providers.ChapterMeta

	// Parse page 1
	p.extractChapters(doc, &chapters, 1)

	// Discover last page number
	maxPage := 1
	doc.Find("ul.pagination li a, .pagination a").Each(func(i int, sel *goquery.Selection) {
		text := strings.TrimSpace(sel.Text())
		if pageNum, err := strconv.Atoi(text); err == nil {
			if pageNum > maxPage {
				maxPage = pageNum
			}
		}
	})

	// Fetch subsequent pages sequentially with a safe delay to avoid Cloudflare rate limit (HTTP 429)
	for page := 2; page <= maxPage; page++ {
		select {
		case <-ctx.Done():
			return nil, ctx.Err()
		default:
		}

		time.Sleep(500 * time.Millisecond)

		resp, err := p.client.R().
			SetContext(ctx).
			SetQueryParam("page", strconv.Itoa(page)).
			Get(chaptersURL)

		if err != nil {
			return nil, fmt.Errorf("chapters request failed for page %d: %w", page, err)
		}

		if resp.IsError() {
			return nil, fmt.Errorf("chapters page %d returned error status: %s", page, resp.Status())
		}

		pageDoc, err := goquery.NewDocumentFromReader(strings.NewReader(resp.String()))
		if err != nil {
			return nil, fmt.Errorf("failed to parse chapters HTML for page %d: %w", page, err)
		}

		p.extractChapters(pageDoc, &chapters, page)
	}

	return chapters, nil
}

func (p *NovelFireProvider) extractChapters(doc *goquery.Document, chapters *[]providers.ChapterMeta, page int) {
	doc.Find("ul.chapter-list li a").Each(func(i int, sel *goquery.Selection) {
		title := strings.TrimSpace(sel.Find(".chapter-title").Text())
		href := sel.AttrOr("href", "")
		if href != "" && strings.HasPrefix(href, "/") {
			href = "https://novelfire.net" + href
		}

		numStr := strings.TrimSpace(sel.Find(".chapter-no").Text())
		index := (page-1)*100 + i + 1
		if numStr != "" {
			if parsed, err := strconv.Atoi(numStr); err == nil {
				index = parsed
			}
		}

		*chapters = append(*chapters, providers.ChapterMeta{
			Index: index,
			Title: title,
			URL:   href,
		})
	})
}

func (p *NovelFireProvider) GetChapterContent(ctx context.Context, chapterURL string) (providers.ChapterContent, error) {
	if err := p.limiter.Wait(ctx); err != nil {
		return providers.ChapterContent{}, err
	}

	resp, err := p.client.R().
		SetContext(ctx).
		Get(chapterURL)

	if err != nil {
		return providers.ChapterContent{}, fmt.Errorf("chapter content request failed: %w", err)
	}

	if resp.IsError() {
		return providers.ChapterContent{}, fmt.Errorf("chapter content returned error status: %s", resp.Status())
	}

	doc, err := goquery.NewDocumentFromReader(strings.NewReader(resp.String()))
	if err != nil {
		return providers.ChapterContent{}, fmt.Errorf("failed to parse chapter HTML: %w", err)
	}

	title := strings.TrimSpace(doc.Find(".chapter-title").Text())
	
	contentSel := doc.Find("#content.clearfix")
	if contentSel.Length() == 0 {
		return providers.ChapterContent{}, fmt.Errorf("content not found at #content.clearfix")
	}

	// Remove scripts, styles, ads
	contentSel.Find("script, style, iframe, .ads, .ad, .google-auto-placed").Remove()

	htmlContent, err := contentSel.Html()
	if err != nil {
		return providers.ChapterContent{}, fmt.Errorf("failed to get inner html: %w", err)
	}

	converter := md.NewConverter("", true, nil)
	markdown, err := converter.ConvertString(htmlContent)
	if err != nil {
		return providers.ChapterContent{}, fmt.Errorf("failed to convert HTML to Markdown: %w", err)
	}

	return providers.ChapterContent{
		Title:        title,
		MarkdownText: strings.TrimSpace(markdown),
	}, nil
}
