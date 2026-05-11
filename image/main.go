package main

import (
	"flag"
	"fmt"
	"log"
	"os"
	"path/filepath"
)

func main() {
	source      := flag.String("source", "", "Source directory with images (required)")
	dest        := flag.String("dest", "", "Destination storage directory (required)")
	workers     := flag.Int("workers", 4, "Number of parallel workers")
	filterScript := flag.String("filter", "", "Path to yolo_filter.py (optional; skips photos without people/animals)")
	pythonBin   := flag.String("python", "", "Python interpreter to use (default: python3)")
	yoloModel   := flag.String("yolo-model", "", "YOLOv8 model file (default: yolov8n.pt)")
	yoloClasses := flag.String("yolo-classes", "", "Comma-separated YOLO classes to keep (default: person,dog,cat,...)")
	flag.Parse()

	if *source == "" || *dest == "" {
		fmt.Fprintln(os.Stderr, "Usage: image-importer -source <dir> -dest <dir> [-workers N] [-filter yolo_filter.py]")
		flag.PrintDefaults()
		os.Exit(1)
	}

	if err := os.MkdirAll(*dest, 0755); err != nil {
		log.Fatalf("Failed to create dest dir: %v", err)
	}

	db, err := NewDB(filepath.Join(*dest, ".index.db"))
	if err != nil {
		log.Fatalf("Failed to init DB: %v", err)
	}
	defer db.Close()

	var yoloFilter *YOLOFilter
	var filteredDir string
	if *filterScript != "" {
		log.Printf("Starting YOLO filter: %s", *filterScript)
		yoloFilter, err = NewYOLOFilter(*pythonBin, *filterScript, *yoloModel, *yoloClasses)
		if err != nil {
			log.Fatalf("Failed to start YOLO filter: %v", err)
		}
		defer yoloFilter.Close()

		filteredDir = filepath.Join(*dest, "filtered")
		if err := os.MkdirAll(filteredDir, 0755); err != nil {
			log.Fatalf("Failed to create filtered dir: %v", err)
		}
	}

	imp := NewImporter(db, *dest, filteredDir, *workers, yoloFilter)
	stats, err := imp.Run(*source)
	if err != nil {
		log.Fatalf("Import failed: %v", err)
	}

	fmt.Printf("\nResults:\n")
	fmt.Printf("  Imported : %d photos\n", stats.Imported)
	fmt.Printf("  Imported : %d videos\n", stats.ImportedVideos)
	fmt.Printf("  Skipped  : %d (duplicates)\n", stats.Skipped)
	fmt.Printf("  Filtered : %d (no people/animals)\n", stats.Filtered)
	fmt.Printf("  Errors   : %d\n", stats.Errors)
}
