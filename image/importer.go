package main

import (
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"github.com/rwcarlsen/goexif/exif"
)

var imageExts = map[string]bool{
	".jpg":  true,
	".jpeg": true,
	".png":  true,
	".tiff": true,
	".tif":  true,
	".heic": true,
	".cr2":  true,
	".nef":  true,
	".arw":  true,
	".dng":  true,
	".raf":  true,
}

var videoExts = map[string]bool{
	".mov":  true, // iPhone основной формат
	".mp4":  true,
	".m4v":  true,
	".hevc": true,
	".avi":  true,
	".mkv":  true,
	".wmv":  true,
	".3gp":  true,
}

func isVideo(path string) bool {
	return videoExts[strings.ToLower(filepath.Ext(path))]
}

type Stats struct {
	Imported       int64
	ImportedVideos int64
	Skipped        int64 // duplicates
	Filtered       int64 // skipped by YOLO (no people/animals)
	Errors         int64
}

type Importer struct {
	db          *DB
	dest        string
	filteredDir string // where to copy YOLO-filtered photos, "" = discard
	workers     int
	filter      *YOLOFilter // optional, nil = no filtering
}

func NewImporter(db *DB, dest, filteredDir string, workers int, filter *YOLOFilter) *Importer {
	return &Importer{db: db, dest: dest, filteredDir: filteredDir, workers: workers, filter: filter}
}

func (imp *Importer) Run(source string) (*Stats, error) {
	jobs := make(chan string, imp.workers*2)

	// воркеры стартуют сразу и ждут файлы из канала
	var stats Stats
	var wg sync.WaitGroup
	for i := 0; i < imp.workers; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for path := range jobs {
				imp.processFile(path, &stats)
			}
		}()
	}

	// Walk пишет в канал по мере нахождения файлов
	log.Printf("Scanning %s ...", source)
	err := walkMedia(source, imp.dest, imp.filteredDir, func(path string) {
		jobs <- path
	})
	close(jobs)
	wg.Wait()

	if err != nil {
		return nil, err
	}
	return &stats, nil
}

func (imp *Importer) processFile(path string, stats *Stats) {
	video := isVideo(path)

	// 1. YOLO-фильтр только для фото
	if !video && imp.filter != nil {
		keep, err := imp.filter.ShouldKeep(path)
		if err != nil {
			log.Printf("[WARN]  filter error %s: %v — importing anyway", filepath.Base(path), err)
		} else if !keep {
			if imp.filteredDir != "" {
				dest := uniquePath(imp.filteredDir, filepath.Base(path))
				if err := copyFile(path, dest); err != nil {
					log.Printf("[WARN]  filtered copy failed %s: %v", filepath.Base(path), err)
				} else {
					log.Printf("[TECH]  %s -> %s", filepath.Base(path), dest)
				}
			} else {
				log.Printf("[TECH]  %s", filepath.Base(path))
			}
			atomic.AddInt64(&stats.Filtered, 1)
			return
		}
	}

	// 2. Хешируем файл
	hash, err := hashFile(path)
	if err != nil {
		log.Printf("[ERROR] hash %s: %v", path, err)
		atomic.AddInt64(&stats.Errors, 1)
		return
	}

	// 3. Определяем дату
	var date time.Time
	if video {
		date, err = videoDate(path)
	} else {
		date, err = imageDate(path)
	}
	currentYear := time.Now().Year()
	if err != nil || date.Year() > currentYear {
		info, statErr := os.Stat(path)
		if statErr != nil {
			log.Printf("[ERROR] stat %s: %v", path, statErr)
			atomic.AddInt64(&stats.Errors, 1)
			return
		}
		if err == nil {
			log.Printf("[WARN]  future EXIF date (%d) for %s, using mtime", date.Year(), filepath.Base(path))
		} else {
			log.Printf("[WARN]  no metadata date for %s, using mtime", filepath.Base(path))
		}
		date = info.ModTime()
	}

	// 4. Формируем путь назначения
	baseDir := imp.dest
	if video {
		baseDir = filepath.Join(imp.dest, "video")
	}
	destDir := filepath.Join(
		baseDir,
		fmt.Sprintf("%04d", date.Year()),
		fmt.Sprintf("%02d", int(date.Month())),
		fmt.Sprintf("%02d", date.Day()),
	)
	if err := os.MkdirAll(destDir, 0755); err != nil {
		log.Printf("[ERROR] mkdir %s: %v", destDir, err)
		atomic.AddInt64(&stats.Errors, 1)
		return
	}

	destPath := uniquePath(destDir, filepath.Base(path))

	// 5. Копируем файл
	if err := copyFile(path, destPath); err != nil {
		log.Printf("[ERROR] copy %s: %v", path, err)
		atomic.AddInt64(&stats.Errors, 1)
		return
	}

	// 6. Пытаемся вставить хеш в БД (атомарно, INSERT OR IGNORE)
	inserted, err := imp.db.TryInsert(hash, destPath)
	if err != nil {
		log.Printf("[ERROR] db insert %s: %v", path, err)
		os.Remove(destPath)
		atomic.AddInt64(&stats.Errors, 1)
		return
	}

	if !inserted {
		os.Remove(destPath)
		log.Printf("[SKIP]  duplicate: %s", filepath.Base(path))
		atomic.AddInt64(&stats.Skipped, 1)
		return
	}

	log.Printf("[OK]    %s -> %s", filepath.Base(path), destPath)
	if video {
		atomic.AddInt64(&stats.ImportedVideos, 1)
	} else {
		atomic.AddInt64(&stats.Imported, 1)
	}
}

func walkMedia(source, dest, filteredDir string, fn func(path string)) error {
	absSource, err := filepath.Abs(source)
	if err != nil {
		return err
	}
	absDest, err := filepath.Abs(dest)
	if err != nil {
		return err
	}
	absFiltered := ""
	if filteredDir != "" {
		absFiltered, _ = filepath.Abs(filteredDir)
	}

	return filepath.Walk(absSource, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}
		if info.IsDir() {
			absPath, _ := filepath.Abs(path)
			if absPath == absDest || (absFiltered != "" && absPath == absFiltered) {
				return filepath.SkipDir
			}
			log.Printf("Scanning dir: %s", path)
			return nil
		}
		ext := strings.ToLower(filepath.Ext(path))
		if imageExts[ext] || videoExts[ext] {
			fn(path)
		}
		return nil
	})
}

func hashFile(path string) (string, error) {
	f, err := os.Open(path)
	if err != nil {
		return "", err
	}
	defer f.Close()

	h := sha256.New()
	if _, err := io.Copy(h, f); err != nil {
		return "", err
	}
	return fmt.Sprintf("%x", h.Sum(nil)), nil
}

func imageDate(path string) (time.Time, error) {
	f, err := os.Open(path)
	if err != nil {
		return time.Time{}, err
	}
	defer f.Close()

	x, err := exif.Decode(f)
	if err != nil {
		return time.Time{}, err
	}
	return x.DateTime()
}

// videoDate extracts creation time from video metadata via ffprobe.
func videoDate(path string) (time.Time, error) {
	out, err := exec.Command("ffprobe",
		"-v", "quiet",
		"-print_format", "json",
		"-show_entries", "format_tags=creation_time",
		path,
	).Output()
	if err != nil {
		return time.Time{}, err
	}

	var result struct {
		Format struct {
			Tags struct {
				CreationTime string `json:"creation_time"`
			} `json:"tags"`
		} `json:"format"`
	}
	if err := json.Unmarshal(out, &result); err != nil {
		return time.Time{}, err
	}

	raw := result.Format.Tags.CreationTime
	if raw == "" {
		return time.Time{}, fmt.Errorf("no creation_time tag")
	}

	// ffprobe returns RFC3339: "2024-01-15T10:30:00.000000Z"
	t, err := time.Parse(time.RFC3339Nano, raw)
	if err != nil {
		t, err = time.Parse("2006-01-02T15:04:05Z", raw)
	}
	return t, err
}

func uniquePath(dir, filename string) string {
	candidate := filepath.Join(dir, filename)
	if _, err := os.Stat(candidate); os.IsNotExist(err) {
		return candidate
	}
	ext := filepath.Ext(filename)
	name := strings.TrimSuffix(filename, ext)
	for i := 1; ; i++ {
		candidate = filepath.Join(dir, fmt.Sprintf("%s_%d%s", name, i, ext))
		if _, err := os.Stat(candidate); os.IsNotExist(err) {
			return candidate
		}
	}
}

func copyFile(src, dst string) error {
	in, err := os.Open(src)
	if err != nil {
		return err
	}
	defer in.Close()

	out, err := os.Create(dst)
	if err != nil {
		return err
	}
	defer out.Close()

	_, err = io.Copy(out, in)
	return err
}
