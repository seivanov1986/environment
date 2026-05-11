BINARY  := image-importer
VENV    := ./venv
PYTHON  := $(VENV)/bin/python3
MODEL   := yolov8n.pt
FILTER  := ./yolo_filter.py

# Параметры запуска: make run SOURCE=/path/to/photos DEST=/path/to/storage
SOURCE  ?= ./source
DEST    ?= ./dest

.PHONY: all build venv model run clean

all: build venv model

## Сборка Go бинарника
build:
	go build -o $(BINARY) .

## Создание venv и установка зависимостей
venv: $(PYTHON)

$(PYTHON):
	python3 -m venv $(VENV)
	$(PYTHON) -m pip install --upgrade pip --quiet
	$(PYTHON) -m pip install -r requirements.txt --timeout 300

## Скачивание модели YOLOv8n
model: $(MODEL)

$(MODEL):
	$(PYTHON) -c "from ultralytics import YOLO; YOLO('$(MODEL)')"

## Запуск импортера
run: $(BINARY) $(PYTHON) $(MODEL)
	./$(BINARY) \
		-source "$(SOURCE)" \
		-dest   "$(DEST)" \
		-filter "$(FILTER)" \
		-python "$(PYTHON)" \
		-yolo-model "$(MODEL)"

## Удалить бинарник и venv
clean:
	rm -f $(BINARY)
	rm -rf $(VENV)
