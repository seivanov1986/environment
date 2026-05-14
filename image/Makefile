VENV    := ./venv
PYTHON  := $(VENV)/bin/python3
MODEL   := yolov8n.pt
SCRIPT  := ./importer.py

# Параметры запуска: make run SOURCE=/path/to/photos DEST=/path/to/storage
SOURCE  ?= ./source
DEST    ?= ./dest

.PHONY: all venv model run clean

all: venv model

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
run: $(PYTHON) $(MODEL)
	$(PYTHON) $(SCRIPT) \
		-source "$(SOURCE)" \
		-dest   "$(DEST)" \
		-filter \
		-yolo-model "$(MODEL)"

## Удалить venv
clean:
	rm -rf $(VENV)
